import unittest

from scripts.spikes.feishu_spike import check_config


REQUIRED = {
    "FEISHU_APP_ID": "fixture-app-id",
    "FEISHU_APP_SECRET": "fixture-app-secret",
    "FEISHU_VERIFICATION_TOKEN": "fixture-verification-token",
    "FEISHU_ENCRYPT_KEY": "fixture-encrypt-key",
    "FEISHU_TEST_USER_OPEN_ID": "fixture-user-id",
    "FEISHU_TEST_CHAT_ID": "fixture-chat-id",
    "FEISHU_TEST_BITABLE_APP_TOKEN": "fixture-bitable-app",
    "FEISHU_TEST_BITABLE_TABLE_ID": "fixture-bitable-table",
    "FEISHU_TEST_DOCUMENT_PARENT_TOKEN": "fixture-document-parent",
}


class FeishuSpikeConfigTest(unittest.TestCase):
    def test_complete_config_is_ready_without_exposing_secret_values(self):
        result = check_config(REQUIRED)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["missing"], [])
        self.assertNotIn("fixture-app-secret", repr(result))
        self.assertNotIn("fixture-encrypt-key", repr(result))

    def test_missing_config_is_unverified_and_lists_only_variable_names(self):
        result = check_config({})

        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["missing"], sorted(REQUIRED))
        self.assertNotIn("fixture-app-secret", repr(result))


if __name__ == "__main__":
    unittest.main()
