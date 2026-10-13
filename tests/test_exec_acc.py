from eval.exec_acc import exec_match, results_match


def test_order_ignored_without_order_by(school_db):
    gold = "SELECT student_name FROM students WHERE home_city = 'Pune'"
    pred = "SELECT student_name FROM students WHERE home_city = 'Pune' ORDER BY student_name DESC"
    assert exec_match(gold, pred, school_db)["correct"]


def test_order_enforced_with_order_by(school_db):
    gold = "SELECT student_name FROM students ORDER BY age"
    wrong = "SELECT student_name FROM students ORDER BY age DESC"
    right = "SELECT student_name FROM students ORDER BY age ASC"
    assert not exec_match(gold, wrong, school_db)["correct"]
    assert exec_match(gold, right, school_db)["correct"]


def test_multiset_counts_duplicates():
    assert not results_match([(1,), (1,), (2,)], [(1,), (2,), (2,)], ordered=False)
    assert results_match([(1,), (2,), (1,)], [(1,), (1,), (2,)], ordered=False)


def test_float_rounding():
    assert results_match([(0.1 + 0.2,)], [(0.3,)], ordered=True)
    assert not results_match([(0.3,)], [(0.31,)], ordered=True)


def test_pred_error_is_incorrect(school_db):
    res = exec_match("SELECT 1", "SELECT nope FROM students", school_db)
    assert not res["correct"] and "no such column" in res["pred_error"]


def test_unsafe_pred_is_incorrect_and_not_executed(school_db):
    res = exec_match("SELECT count(*) FROM students", "DELETE FROM students", school_db)
    assert not res["correct"] and "GuardError" in res["pred_error"]
