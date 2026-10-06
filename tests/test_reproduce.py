import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import reproduce


ROOT = Path(__file__).resolve().parents[1]


class ResumeValidationTests(unittest.TestCase):
    def _valid_population_output(self, destination: Path) -> list[dict]:
        for relative in reproduce.declared_outputs("population-1"):
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "results" / relative, target)
        return [{"task": "population-1", "exit_code": 0,
                 "science_inputs_sha256": reproduce.science_inputs_fingerprint()}]

    def test_resume_recomputes_when_science_inputs_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            records = self._valid_population_output(out)
            self.assertTrue(reproduce.task_ready_to_skip("population-1", out, records))
            with patch.object(reproduce, "science_inputs_fingerprint", return_value="changed"):
                self.assertFalse(reproduce.task_ready_to_skip("population-1", out, records))
            records[0].pop("science_inputs_sha256")
            self.assertFalse(reproduce.task_ready_to_skip("population-1", out, records))

    def test_science_fingerprint_tracks_input_bytes_and_source_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inputs").mkdir()
            (root / "src").mkdir()
            fixture = root / "inputs" / "finite.json"
            fixture.write_text('[1]\n')
            first = reproduce.science_inputs_fingerprint(root)
            fixture.write_text('[2]\n')
            second = reproduce.science_inputs_fingerprint(root)
            self.assertNotEqual(first, second)
            (root / "src" / "new.py").write_text('# owned finite source\n')
            self.assertNotEqual(second, reproduce.science_inputs_fingerprint(root))

    def test_resume_recomputes_when_output_is_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            records = self._valid_population_output(out)
            self.assertTrue(reproduce.task_ready_to_skip("population-1", out, records))
            (out / "population-1-summary.json").unlink()
            self.assertFalse(reproduce.task_ready_to_skip("population-1", out, records))

    def test_resume_recomputes_when_output_is_corrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            records = self._valid_population_output(out)
            self.assertTrue(reproduce.task_ready_to_skip("population-1", out, records))
            (out / "population-1.csv").write_text("corrupted\n")
            self.assertFalse(reproduce.task_ready_to_skip("population-1", out, records))


if __name__ == "__main__":
    unittest.main()
