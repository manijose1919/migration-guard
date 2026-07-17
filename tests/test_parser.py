from migration_guard.parser import extract_table, parse_sql


def test_split_counts_statements_and_ignores_comments():
    sql = """
    -- a comment
    ALTER TABLE users ADD COLUMN a int;
    -- another
    DROP TABLE widgets;
    """
    stmts = parse_sql(sql)
    assert len(stmts) == 2
    assert stmts[0].action == "ALTER"
    assert stmts[1].action == "DROP"
    # comments are stripped from the normalized form
    assert "COMMENT" not in stmts[0].normalized


def test_line_numbers_are_correct_even_with_repeated_keyword():
    sql = (
        "-- header\n"           # line 1
        "\n"                     # line 2
        "CREATE INDEX i ON t (c);\n"   # line 3
        "\n"                     # line 4
        "ALTER TABLE orders ALTER COLUMN total TYPE bigint;\n"  # line 5 (ALTER twice)
        "\n"                     # line 6
        "ALTER TABLE users DROP COLUMN old;\n"  # line 7
    )
    stmts = parse_sql(sql)
    assert [s.line for s in stmts] == [3, 5, 7]


def test_normalized_is_uppercase_and_collapsed():
    stmts = parse_sql("alter   table   users\n  add column a int;")
    assert stmts[0].normalized == "ALTER TABLE USERS ADD COLUMN A INT"


def test_extract_table():
    assert extract_table("ALTER TABLE USERS ADD COLUMN A INT") == "users"
    assert extract_table("CREATE INDEX I ON ORDERS (C)") == "orders"
    assert extract_table("DROP TABLE IF EXISTS WIDGETS") == "widgets"
    assert extract_table('ALTER TABLE "PUBLIC"."USERS" DROP COLUMN X') is not None
    assert extract_table("SELECT 1") is None


def test_empty_input_yields_no_statements():
    assert parse_sql("") == []
    assert parse_sql("   -- only a comment\n") == []
