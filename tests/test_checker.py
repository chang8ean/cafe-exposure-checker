"""시트·네이버 없이 도는 테스트.   python -m unittest discover tests"""
import unittest
from datetime import date

from checker import autosub, exposure, rules
from checker.sheet import MG_HEADERS, parse_mulgil

CFG = {"fresh_days": 30, "recent_days": 60, "old_days": 90,
       "dead_cafes": ["closedcafe"], "dead_ids": ["goneid"]}


def mg(*rows):
    return parse_mulgil([MG_HEADERS] + [list(r) for r in rows])


class ExposureTest(unittest.TestCase):
    def test_extract_id(self):
        self.assertEqual(exposure.extract_id("https://cafe.naver.com/mycafe/123456"), "123456")
        self.assertEqual(exposure.extract_id("https://blog.naver.com/me/223344556677"), "223344556677")
        self.assertEqual(exposure.extract_id(
            "https://cafe.naver.com/f-e/cafes/1/articles/98765?x=1"), "98765")
        self.assertEqual(exposure.extract_id(
            "https://cafe.naver.com/c?iframe_url_utf8=%2FArticleRead.nhn%253Fclubid%3D1%2526articleid%3D555666"),
            "555666")
        self.assertIsNone(exposure.extract_id("https://example.com/1"))

    def test_query_has_no_spaces(self):
        self.assertEqual(exposure.query_of(" 간수치 높은 이유 "), "간수치높은이유")

    def test_number_outside_url_is_not_exposure(self):
        html = '<img src="1766731093373_unnamed.jpg"> <a href="https://cafe.naver.com/other/731093">'
        self.assertFalse(exposure.check("https://cafe.naver.com/mycafe/731093", html)["exposed"])
        html2 = html + '<a href="https://cafe.naver.com/mycafe/731093">'
        self.assertTrue(exposure.check("https://cafe.naver.com/mycafe/731093", html2)["exposed"])


class RulesTest(unittest.TestCase):
    def test_status(self):
        ns = rules.next_status
        self.assertEqual(ns("", True, 1, 21), "Y")
        self.assertEqual(ns("", False, 5, 21), "W")
        self.assertEqual(ns("W", False, 21, 21), "N")
        self.assertEqual(ns("W", False, None, 21), "W")
        self.assertEqual(ns("Y", False, 100, 21), "D")
        self.assertEqual(ns("D", False, 100, 21), "D")
        self.assertEqual(ns("D", True, 100, 21), "Y")
        self.assertEqual(ns("N", False, 100, 21), "N")

    def test_select_priority_and_dead(self):
        today = date(2026, 10, 20)       # 화요일
        rows, _ = mg(
            ["2026. 10. 15", "메인", "카페A", "id1", "새글", "", "W", "", "https://cafe.naver.com/a/100001"],
            ["2026. 6. 1", "메인", "카페A", "id1", "옛D", "", "D", "", "https://cafe.naver.com/a/100002"],
            ["2026. 8. 1", "메인", "카페A", "id1", "옛Y", "", "Y", "", "https://cafe.naver.com/a/100003"],
            ["2026. 10. 1", "메인", "카페B", "id2", "폐쇄", "", "", "", "https://cafe.naver.com/closedcafe/1"],
            ["2026. 10. 1", "메인", "카페C", "goneid", "삭제", "", "", "", "https://cafe.naver.com/c/2"],
        )
        got = [r["keyword"] for r in rules.select_rows(rows, today, CFG)]
        self.assertEqual(got, ["새글", "옛Y"])          # 90일 넘은 D 는 일요일에만
        sunday = [r["keyword"] for r in rules.select_rows(rows, date(2026, 10, 25), CFG)]
        self.assertIn("옛D", sunday)

    def test_resume_matches_by_keyword_and_url(self):
        rows, _ = mg(["2026. 10. 15", "메인", "카페A", "id1", "새 글", "", "W", "",
                      "https://cafe.naver.com/a/100001"])
        keys = {("새글", "https://cafe.naver.com/a/100001")}
        self.assertEqual(len(rules.select_rows(rows, date(2026, 10, 20), CFG, keys)), 1)


class MulgilTest(unittest.TestCase):
    def test_sub_inherits_from_main(self):
        rows, _ = mg(["2026. 10. 1", "메인", "카페A", "id1", "메인키", "", "", "", "https://cafe.naver.com/a/111111"],
                     ["", "서브", "", "", "서브키", "", "", "", ""])
        self.assertEqual(rows[1]["url"], "https://cafe.naver.com/a/111111")
        self.assertEqual(rows[1]["date"], "2026. 10. 1")
        self.assertEqual(rows[1]["kind"], "서브")


class AutosubTest(unittest.TestCase):
    def setUp(self):
        self.rows, self.idx = mg(
            ["2026. 9. 1", "메인", "카페A", "id1", "간에좋은음식", "", "Y", "", "https://cafe.naver.com/a/111111"],
            ["2026. 9. 1", "서브", "카페A", "id1", "간에좋은차", "", "Y", "", "https://cafe.naver.com/a/111111"],
            ["2026. 10. 1", "메인", "카페B", "id2", "간수치", "", "N", "메모", "https://cafe.naver.com/b/222222"],
        )
        holder = self.rows[0]
        self.cov = [{"row": 4, "bigo": "메모", "keyword": "간 수치", "holder": holder}]

    def test_plan_inserts_under_group(self):
        p = autosub.plan(self.rows, self.cov, {"간수치": 500}, date(2026, 10, 20), 100, self.idx)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]["after"], 3)                 # 묶음 마지막(서브) 아래
        v = p[0]["values"]
        self.assertEqual(v[self.idx["구분"]], "서브")
        self.assertEqual(v[self.idx["노출여부"]], "Y")
        self.assertEqual(v[self.idx["URL"]], "https://cafe.naver.com/a/111111")

    def test_plan_skips_small_or_existing(self):
        self.assertEqual(autosub.plan(self.rows, self.cov, {"간수치": 80}, date(2026, 10, 20), 100, self.idx), [])
        cov = [{**self.cov[0], "keyword": "간에 좋은 차"}]
        self.assertEqual(autosub.plan(self.rows, cov, {"간에좋은차": 999}, date(2026, 10, 20), 100, self.idx), [])

    def test_bigo_keeps_human_note_and_replaces_auto_note(self):
        u = autosub.bigo_updates(self.cov, date(2026, 10, 20))
        self.assertTrue(u[0][1].startswith("메모 | 다른 글로 노출중(10/20)"))
        again = autosub.bigo_updates([{**self.cov[0], "bigo": u[0][1]}], date(2026, 10, 21))
        self.assertEqual(again[0][1].count("다른 글로 노출중"), 1)
        self.assertIn("(10/21)", again[0][1])


if __name__ == "__main__":
    unittest.main()
