"""Atomic append-only annotation batches in the authoritative run database."""

from alignmenter.schemas.review import Annotation
from alignmenter.storage.evaluations import EvaluationStore, _decode, _encode


class ReviewStore(EvaluationStore):
    @staticmethod
    def _annotations(db):
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='review_schema'").fetchone()
        if not exists:
            return []
        if db.execute("SELECT version FROM review_schema").fetchone()[0] != 1:
            raise ValueError("Unsupported review database version")
        return [_decode(Annotation, row) for row in db.execute("SELECT payload,digest FROM annotations ORDER BY rowid")]

    def annotations(self):
        with self.transaction() as db:
            return self._annotations(db)

    def append_annotations(self, annotations):
        with self.transaction(write=True) as db:
            existing = self._annotations(db)
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='review_schema'").fetchone():
                db.execute("CREATE TABLE review_schema (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL)")
                db.execute("INSERT INTO review_schema VALUES (1,1)")
                db.execute("CREATE TABLE annotations (id TEXT PRIMARY KEY, review_key TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL)")
            by_id = {a.id: a for a in existing}
            superseded = {a.supersedes for a in existing if a.supersedes is not None}
            for annotation in annotations:
                previous = by_id.get(annotation.id)
                if previous is not None:
                    if previous.model_dump(exclude={"recorded_at"}) != annotation.model_dump(exclude={"recorded_at"}):
                        raise ValueError("An annotation ID cannot overwrite a previous annotation")
                    continue
                active = [a for a in by_id.values() if a.id not in superseded and a.review_key == annotation.review_key
                          and a.role == annotation.role and (a.reviewer == annotation.reviewer or a.role == "adjudication")]
                if annotation.supersedes is not None:
                    prior = by_id.get(annotation.supersedes)
                    if prior is None or prior not in active:
                        raise ValueError("Supersedes must reference the active annotation for this review and role")
                elif active:
                    raise ValueError("Updating a review requires explicit supersedes; annotations are append-only")
                db.execute("INSERT INTO annotations VALUES (?,?,?,?)", (str(annotation.id), annotation.review_key, *_encode(annotation)))
                self._event(db, "review_annotation_saved", str(annotation.id))
                by_id[annotation.id] = annotation
                if annotation.supersedes is not None:
                    superseded.add(annotation.supersedes)


def active_annotations(annotations):
    superseded = {a.supersedes for a in annotations if a.supersedes is not None}
    return [a for a in annotations if a.id not in superseded]
