"""TDD for reffreshness.py — typed registry loader (P0-2). stdlib only.
Run: python -m unittest test_reffreshness -v
"""
import json, os, sys, tempfile, unittest
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reffreshness as F

TODAY = date(2026, 9, 1)


def _reg(records):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "r.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"records": records}, f)
    return p


def _rec(**kw):
    base = {"id": "x", "claim": "c", "status": "observed", "source_refs": ["s"],
            "observed_at": "2026-09-01", "effective_at": None, "ttl_days": 30, "scope": "t"}
    base.update(kw)
    return base


class Load(unittest.TestCase):
    def test_missing_file(self):
        recs, iss = F.load_registry(os.path.join(tempfile.mkdtemp(), "nope.json"))
        self.assertEqual(recs, [])
        self.assertTrue(any("missing" in i for i in iss))

    def test_corrupt_json(self):
        d = tempfile.mkdtemp(); p = os.path.join(d, "r.json")
        open(p, "w").write("{not json")
        recs, iss = F.load_registry(p)
        self.assertEqual(recs, [])
        self.assertTrue(any("unreadable" in i for i in iss))

    def test_missing_field_flagged(self):
        recs, iss = F.load_registry(_reg([{"id": "a", "status": "observed"}]))
        self.assertEqual(recs, [])
        self.assertTrue(any("missing fields" in i for i in iss))

    def test_duplicate_id_flagged(self):
        recs, iss = F.load_registry(_reg([_rec(id="dup"), _rec(id="dup")]))
        self.assertEqual(len(recs), 1)
        self.assertTrue(any("duplicate id" in i for i in iss))

    def test_bad_status_flagged(self):
        recs, iss = F.load_registry(_reg([_rec(id="a", status="madeup")]))
        self.assertTrue(any("invalid status" in i for i in iss))

    def test_bad_date_flagged(self):
        recs, iss = F.load_registry(_reg([_rec(id="a", observed_at="nope")]))
        self.assertTrue(any("unparseable date" in i for i in iss))

    def test_bad_ttl_flagged(self):
        recs, iss = F.load_registry(_reg([_rec(id="a", ttl_days=0)]))
        self.assertTrue(any("ttl_days" in i for i in iss))

    def test_valid_loads(self):
        recs, iss = F.load_registry(_reg([_rec(id="ok")]))
        self.assertEqual(len(recs), 1)
        self.assertEqual(iss, [])


class StrictLoad(unittest.TestCase):
    """Codex 3rd review: loader crashed on some corruption and clean-loaded bad field types."""
    def test_top_level_list_does_not_crash(self):
        d = tempfile.mkdtemp(); p = os.path.join(d, "r.json")
        open(p, "w").write("[1,2,3]")
        recs, iss = F.load_registry(p)
        self.assertEqual(recs, [])
        self.assertTrue(any("root must be an object" in i for i in iss))

    def test_list_id_does_not_crash(self):
        recs, iss = F.load_registry(_reg([_rec(id=["a", "b"])]))
        self.assertEqual(recs, [])
        self.assertTrue(any("id must be a non-empty string" in i for i in iss))

    def test_bool_ttl_rejected(self):
        recs, iss = F.load_registry(_reg([_rec(id="a", ttl_days=True)]))
        self.assertTrue(any("ttl_days" in i for i in iss))

    def test_empty_source_refs_rejected(self):
        recs, iss = F.load_registry(_reg([_rec(id="a", source_refs=[])]))
        self.assertTrue(any("source_refs" in i for i in iss))

    def test_nonstring_claim_rejected(self):
        recs, iss = F.load_registry(_reg([_rec(id="a", claim=9)]))
        self.assertTrue(any("claim" in i for i in iss))

    def test_future_observed_is_corrupt(self):
        e = F.evaluate([_rec(observed_at="2030-01-01")], today=TODAY)[0]
        self.assertEqual(e["freshness"], "corrupt")

    def test_list_status_does_not_crash(self):   # C4.1: unhashable status must be an issue, not a TypeError
        recs, iss = F.load_registry(_reg([_rec(id="a", status=["observed"])]))
        self.assertEqual(recs, [])
        self.assertTrue(any("status must be a string" in i for i in iss))

    def test_null_source_ref_item_rejected(self):   # C4.2: [null] source_refs must not clean-load
        recs, iss = F.load_registry(_reg([_rec(id="a", source_refs=[None])]))
        self.assertEqual(recs, [])
        self.assertTrue(any("source_refs items" in i for i in iss))

    def test_nonstring_scope_rejected(self):   # C4.2: scope shape validated
        recs, iss = F.load_registry(_reg([_rec(id="a", scope=[])]))
        self.assertEqual(recs, [])
        self.assertTrue(any("scope" in i for i in iss))


class Evaluate(unittest.TestCase):
    def test_fresh_within_ttl(self):
        e = F.evaluate([_rec(observed_at="2026-08-20", ttl_days=30)], today=TODAY)[0]
        self.assertEqual(e["freshness"], "fresh")

    def test_stale_past_ttl(self):
        e = F.evaluate([_rec(observed_at="2026-07-01", ttl_days=30)], today=TODAY)[0]
        self.assertEqual(e["freshness"], "stale")

    def test_pending_future_effective(self):
        e = F.evaluate([_rec(effective_at="2026-09-15")], today=TODAY)[0]
        self.assertEqual(e["freshness"], "pending")

    def test_unverified_status(self):
        e = F.evaluate([_rec(status="partially-verified")], today=TODAY)[0]
        self.assertEqual(e["freshness"], "unverified")

    def test_pending_beats_stale_and_unverified(self):
        # future effective_at is 'pending' even if old observed_at
        e = F.evaluate([_rec(observed_at="2026-01-01", ttl_days=30, effective_at="2026-12-01")], today=TODAY)[0]
        self.assertEqual(e["freshness"], "pending")

    def test_evaluate_does_not_mutate(self):
        r = _rec()
        before = json.dumps(r, sort_keys=True)
        F.evaluate([r], today=TODAY)
        self.assertEqual(json.dumps(r, sort_keys=True), before)


class RegistryCheckHook(unittest.TestCase):
    def test_warns_on_stale_and_pending(self):
        p = _reg([_rec(id="fresh1", observed_at="2026-08-25", ttl_days=30),
                  _rec(id="stale1", observed_at="2026-01-01", ttl_days=30),
                  _rec(id="pend1", effective_at="2026-12-01")])
        w = F.registry_check(p, today=TODAY)
        self.assertTrue(any("stale1" in x for x in w))
        self.assertTrue(any("pend1" in x for x in w))
        self.assertFalse(any("fresh1" in x for x in w))

    def test_dead_within_ttl_is_warned(self):   # C4.4: dead/degraded health must not be machine-silent
        p = _reg([_rec(id="deadtool", status="dead", observed_at="2026-08-30", ttl_days=90)])
        w = F.registry_check(p, today=TODAY)
        self.assertTrue(any("deadtool" in x and "dead" in x for x in w))


class RealRegistry(unittest.TestCase):
    def test_shipped_registry_loads_clean(self):
        recs, iss = F.load_registry(F.DEFAULT_REGISTRY)
        self.assertEqual(iss, [], f"shipped facts.registry.json must be valid: {iss}")
        self.assertTrue(len(recs) >= 10)
        # F-001 must evaluate as pending until 2026-09-15
        e = {x["id"]: x for x in F.evaluate(recs, today=TODAY)}
        self.assertEqual(e["F-001"]["freshness"], "pending")
        self.assertEqual(e["F-003"]["freshness"], "unverified")


if __name__ == "__main__":
    unittest.main()
