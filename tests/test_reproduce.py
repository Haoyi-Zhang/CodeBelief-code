import json
import shutil
import tempfile
import unittest
from pathlib import Path

import reproduce


ROOT = Path(__file__).resolve().parents[1]


class ResumeValidationTests(unittest.TestCase):
    def _valid_population_output(self, destination: Path) -> list[dict]:
        for relative in reproduce.declared_outputs("population-1"):
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "results" / relative, target)
        return [{"task": "population-1", "exit_code": 0}]

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
