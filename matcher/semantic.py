"""Semantic-rejection backends for the matcher (PLAN.md pipeline step 2).

The classifier's job is rejection, not identity: it answers "is this photo
even the right *kind* of thing?" ("want says church; photo is a selfie").
A backend is a callable `(photo_path, want) -> True | False | None`:

    True   photo content is compatible with the want's classifier_labels
    False  incompatible — the matcher drops the candidate
    None   can't tell — the matcher caps the candidate at worth_a_look

Backends:

    ClipChecker     real implementation: open_clip zero-shot scoring of the
                    photo against "a photo of a <label>" prompts vs. a fixed
                    set of negative prompts (selfie, food, pet, screenshot...).
                    Needs `pip install torch open_clip_torch` and network
                    access to download weights on first use. ViT-B-32 is a
                    desktop stand-in for the MobileCLIP-class model the
                    eventual mobile client would ship.

    ExifTagChecker  test-only backend: trusts a ground-truth content label
                    planted in EXIF UserComment by make_test_library.py.
                    Exists so the matcher's semantic integration (drop /
                    cap / allow auto_suggest) is testable in environments
                    where model weights cannot be downloaded. Never use it
                    on real libraries — real EXIF comments are arbitrary.
"""

NEGATIVE_PROMPTS = [
    "a selfie",
    "a portrait of a person",
    "a group photo of people",
    "food on a plate",
    "a pet animal",
    "a screenshot",
    "a photo of a document or receipt",
    "the interior of a car",
]


class ClipChecker:
    def __init__(self, model_name="ViT-B-32", pretrained="laion2b_s34b_b79k",
                 agree_threshold=0.6, reject_threshold=0.2):
        import open_clip  # deferred: heavy, optional dependency
        import torch

        self.torch = torch
        self.open_clip = open_clip
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained
        )
        self.model.eval()
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.agree_threshold = agree_threshold
        self.reject_threshold = reject_threshold
        self._image_cache = {}
        self._text_cache = {}

    def _image_features(self, path):
        key = str(path)
        if key not in self._image_cache:
            from PIL import Image

            with self.torch.no_grad():
                img = self.preprocess(Image.open(path).convert("RGB")).unsqueeze(0)
                feats = self.model.encode_image(img)
                self._image_cache[key] = feats / feats.norm(dim=-1, keepdim=True)
        return self._image_cache[key]

    def _text_features(self, labels):
        key = tuple(labels)
        if key not in self._text_cache:
            prompts = [f"a photo of a {l}" for l in labels] + NEGATIVE_PROMPTS
            with self.torch.no_grad():
                toks = self.tokenizer(prompts)
                feats = self.model.encode_text(toks)
                self._text_cache[key] = feats / feats.norm(dim=-1, keepdim=True)
        return self._text_cache[key]

    def __call__(self, photo_path, want):
        labels = want["subject"].get("classifier_labels") or []
        if not labels:
            return None
        image = self._image_features(photo_path)
        text = self._text_features(labels)
        probs = (100.0 * image @ text.T).softmax(dim=-1)[0]
        positive = float(probs[: len(labels)].sum())
        if positive >= self.agree_threshold:
            return True
        if positive <= self.reject_threshold:
            return False
        return None


class ExifTagChecker:
    USERCOMMENT_TAG = 37510  # Exif IFD UserComment

    def __init__(self):
        self._cache = {}

    def _planted_label(self, path):
        key = str(path)
        if key not in self._cache:
            import piexif

            label = None
            try:
                raw = piexif.load(key)["Exif"].get(self.USERCOMMENT_TAG)
                if raw:
                    # piexif stores UserComment with an 8-byte encoding prefix
                    label = raw[8:].decode("ascii", "ignore").strip() or None
            except Exception:
                pass
            self._cache[key] = label
        return self._cache[key]

    def __call__(self, photo_path, want):
        label = self._planted_label(photo_path)
        if label is None:
            return None
        return label in (want["subject"].get("classifier_labels") or [])


def build_checker(name):
    """Map a --semantic CLI value to a backend instance (None = stub off)."""
    if name == "off":
        return None
    if name == "clip":
        return ClipChecker()
    if name == "exif-tag":
        return ExifTagChecker()
    raise ValueError(f"unknown semantic backend: {name}")
