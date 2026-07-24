import unittest

from scripts.spikes.github_spike import check_config as check_github_config
from scripts.spikes.llm_spike import check_config as check_llm_config


class GitHubAndLlmSpikeConfigTest(unittest.TestCase):
    def test_github_requires_pat_and_two_test_repositories(self):
        result = check_github_config(
            {
                "GITHUB_PAT": "fixture-value-a",
                "GITHUB_TEST_REPO_1": "owner/one",
                "GITHUB_TEST_REPO_2": "owner/two",
            }
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["missing"], [])
        self.assertNotIn("fixture-value-a", repr(result))

    def test_github_without_credentials_is_unverified(self):
        result = check_github_config({})

        self.assertEqual(result["status"], "unverified")
        self.assertEqual(
            result["missing"],
            ["GITHUB_PAT", "GITHUB_TEST_REPO_1", "GITHUB_TEST_REPO_2"],
        )

    def test_llm_requires_endpoint_key_and_model(self):
        result = check_llm_config(
            {
                "LLM_BASE_URL": "https://llm.example.test/v1",
                "LLM_API_KEY": "fixture-value-b",
                "LLM_MODEL": "fixture-model",
            }
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["missing"], [])
        self.assertNotIn("fixture-value-b", repr(result))

    def test_llm_without_credentials_is_unverified(self):
        result = check_llm_config({})

        self.assertEqual(result["status"], "unverified")
        self.assertEqual(
            result["missing"],
            ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"],
        )


if __name__ == "__main__":
    unittest.main()
