from t2s.agent import run_agent
from t2s.config import ArmConfig
from t2s.generate import extract_sql

# No schema linking / few-shot here so the tests need neither the embedder nor Spider.
RETRY2 = ArmConfig("test", link_schema=False, shots=0, max_retries=2)
NO_RETRY = ArmConfig("test0", link_schema=False, shots=0, max_retries=0)

BAD = "```sql\nSELECT nme FROM students\n```"
GOOD = "```sql\nSELECT student_name FROM students WHERE age > 19\n```"


def test_bad_then_good_records_trace(school_db, scripted_llm):
    llm = scripted_llm([BAD, GOOD])
    res = run_agent("Students older than 19?", school_db, RETRY2, llm)
    assert res["status"] == "ok" and res["attempts"] == 2
    assert sorted(res["rows"]) == [("Meera",), ("Ravi",)]
    assert len(res["error_trace"]) == 1
    assert "no such column" in res["error_trace"][0]["error"]
    assert res["tokens_in"] == 200 and res["tokens_out"] == 40
    # the second prompt carries the failed SQL, the error and a column hint
    feedback = llm.calls[1]["messages"][-1]["content"]
    assert "SELECT nme FROM students" in feedback and "no such column" in feedback
    assert "students(student_id, student_name" in feedback
    assert llm.calls[1]["options"]["temperature"] > 0  # retries are sampled, attempt 1 greedy
    assert llm.calls[0]["options"] == {}


def test_stops_after_two_retries(school_db, scripted_llm):
    llm = scripted_llm([BAD])
    res = run_agent("q", school_db, RETRY2, llm)
    assert len(llm.calls) == 3 and res["attempts"] == 3
    assert res["status"] == "error" and len(res["error_trace"]) == 3
    assert [t["attempt"] for t in res["error_trace"]] == [1, 2, 3]


def test_no_retry_arm_makes_one_call(school_db, scripted_llm):
    llm = scripted_llm([BAD, GOOD])
    res = run_agent("q", school_db, NO_RETRY, llm)
    assert len(llm.calls) == 1 and res["status"] == "error"


def test_empty_result_triggers_retry(school_db, scripted_llm):
    empty = "```sql\nSELECT student_name FROM students WHERE home_city = 'pune'\n```"
    fixed = "```sql\nSELECT student_name FROM students WHERE home_city = 'Pune'\n```"
    llm = scripted_llm([empty, fixed])
    res = run_agent("Who lives in Pune?", school_db, RETRY2, llm)
    assert res["attempts"] == 2 and res["error_trace"][0]["kind"] == "empty"
    assert sorted(res["rows"]) == [("Arjun",), ("Ravi",)]


def test_guard_rejection_is_fed_back_and_never_executed(school_db, scripted_llm):
    llm = scripted_llm(["```sql\nDROP TABLE students\n```"])
    res = run_agent("delete everything", school_db, RETRY2, llm)
    assert res["status"] == "guard" and res["attempts"] == 3
    assert all(t["kind"] == "guard" for t in res["error_trace"])
    assert run_agent("count", school_db, NO_RETRY, scripted_llm(
        ["```sql\nSELECT count(*) FROM students\n```"]))["rows"] == [(3,)]


def test_extract_sql_variants():
    assert extract_sql("Here:\n```sql\nSELECT 1;\n```\nDone") == "SELECT 1"
    assert extract_sql("```\nSELECT 2\n```") == "SELECT 2"
    assert extract_sql("The answer is SELECT 3 FROM t;") == "SELECT 3 FROM t"
