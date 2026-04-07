import unittest

from dashboard.services.op_assist_service import OpAssistService


class OpAssistChatParseTests(unittest.TestCase):
    def test_parse_angle_bracket_chat_line(self):
        line = '[23:41:22] [Server thread/INFO]: [Not Secure] <lapiforss> gemma hello'
        parsed = OpAssistService._parse_chat_line(line)
        self.assertEqual(parsed, ('lapiforss', 'gemma hello'))

    def test_parse_colon_chat_line(self):
        line = '[23:41:22] [Server thread/INFO]: lapiforss: gemma hello'
        parsed = OpAssistService._parse_chat_line(line)
        self.assertEqual(parsed, ('lapiforss', 'gemma hello'))


if __name__ == '__main__':
    unittest.main()
