import unittest
from unittest.mock import patch

from dashboard.services.op_assist_service import OpAssistService


class OpAssistPermissionsTests(unittest.TestCase):
    def test_can_execute_commands_only_for_ops_when_beta_enabled(self):
        with patch('dashboard.services.op_assist_service.GEMMA_COMMAND_EXECUTION_BETA', True):
            self.assertTrue(OpAssistService._can_execute_commands_for_user(is_op=True))
            self.assertFalse(OpAssistService._can_execute_commands_for_user(is_op=False))

    def test_can_execute_commands_disabled_when_beta_flag_off(self):
        with patch('dashboard.services.op_assist_service.GEMMA_COMMAND_EXECUTION_BETA', False):
            self.assertFalse(OpAssistService._can_execute_commands_for_user(is_op=True))
            self.assertFalse(OpAssistService._can_execute_commands_for_user(is_op=False))

    def test_non_op_command_decision_is_downgraded_to_chat(self):
        decision = {
            'type': 'command',
            'command': 'time set day',
            'say': 'Setting day now.'
        }
        out = OpAssistService._enforce_permissions_on_decision('lapiforss', decision, can_execute=False)
        self.assertEqual(out.get('type'), 'chat')
        self.assertIn('OP', out.get('say', ''))


if __name__ == '__main__':
    unittest.main()
