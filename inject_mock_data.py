"""
Inject mock student data into the Docere database for course 5273900d-c97c-41d2-95fe-af51e9b8ac41.

Creates:
- 8 mock students (User records)
- Enrollment records linking them to the course
- StudentProfile records with varied engagement
- 5-15 MemoryRecord entries per student with realistic CS course content
"""

import asyncio
import json
import uuid
import random
from datetime import datetime, timedelta, timezone

import asyncpg

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
DB_DSN = "postgresql://docere:docere_dev@localhost:5432/docere"
COURSE_ID = uuid.UUID("5273900d-c97c-41d2-95fe-af51e9b8ac41")

# ──────────────────────────────────────────────
# Student Personas
# ──────────────────────────────────────────────
STUDENTS = [
    {
        "name": "Amira Hassan",
        "email": "amira.hassan@university.edu",
        "engagement": "high",
        "grade": 92.5,
        "confusion_avg": 0.15,
        "interaction_score_avg": 0.88,
        "total_interactions": 47,
        "total_messages": 134,
        "session_duration": 38.5,
        "summary": "Strong student who actively engages with material. Excels at SQL and databases, occasionally struggles with recursion. Asks thoughtful questions and builds on previous concepts.",
    },
    {
        "name": "Jordan Mitchell",
        "email": "jordan.mitchell@university.edu",
        "engagement": "high",
        "grade": 88.0,
        "confusion_avg": 0.22,
        "interaction_score_avg": 0.82,
        "total_interactions": 39,
        "total_messages": 98,
        "session_duration": 32.0,
        "summary": "Consistent performer who asks clarifying questions. Good grasp of loops and conditionals but needs reinforcement on SQL joins and subqueries.",
    },
    {
        "name": "Priya Chakraborty",
        "email": "priya.chakraborty@university.edu",
        "engagement": "medium",
        "grade": 78.5,
        "confusion_avg": 0.45,
        "interaction_score_avg": 0.61,
        "total_interactions": 23,
        "total_messages": 67,
        "session_duration": 22.0,
        "summary": "Shows effort but frequently confused by new topics. Struggles with data types and variable scope. Benefits from worked examples and step-by-step breakdowns.",
    },
    {
        "name": "Marcus Williams",
        "email": "marcus.williams@university.edu",
        "engagement": "medium",
        "grade": 81.0,
        "confusion_avg": 0.35,
        "interaction_score_avg": 0.68,
        "total_interactions": 28,
        "total_messages": 76,
        "session_duration": 25.5,
        "summary": "Steady student who sometimes falls behind. Strong on arrays and loops but weak on SQL and database normalization. Tends to cram before exams.",
    },
    {
        "name": "Elena Rodriguez",
        "email": "elena.rodriguez@university.edu",
        "engagement": "high",
        "grade": 95.0,
        "confusion_avg": 0.10,
        "interaction_score_avg": 0.93,
        "total_interactions": 52,
        "total_messages": 156,
        "session_duration": 42.0,
        "summary": "Top performer who helps peers. Deep understanding of functions, recursion, and SQL. Uses the system to explore advanced topics beyond the syllabus.",
    },
    {
        "name": "Tyler Nakamura",
        "email": "tyler.nakamura@university.edu",
        "engagement": "low",
        "grade": 65.0,
        "confusion_avg": 0.62,
        "interaction_score_avg": 0.38,
        "total_interactions": 11,
        "total_messages": 29,
        "session_duration": 12.0,
        "summary": "Disengaged student who interacts minimally. Shows persistent confusion with fundamental concepts like variables and data types. May need intervention.",
    },
    {
        "name": "Sophia Kim",
        "email": "sophia.kim@university.edu",
        "engagement": "medium",
        "grade": 74.0,
        "confusion_avg": 0.50,
        "interaction_score_avg": 0.55,
        "total_interactions": 19,
        "total_messages": 51,
        "session_duration": 18.0,
        "summary": "Uneven performance across topics. Solid on conditionals and basic loops but deeply confused by SQL and relational databases. Shows improvement when given analogies.",
    },
    {
        "name": "David Okonkwo",
        "email": "david.okonkwo@university.edu",
        "engagement": "inactive",
        "grade": 42.0,
        "confusion_avg": 0.78,
        "interaction_score_avg": 0.15,
        "total_interactions": 4,
        "total_messages": 8,
        "session_duration": 6.0,
        "summary": "Nearly inactive. Last interaction was weeks ago. The few interactions show deep confusion across all topics. At risk of failing the course.",
    },
]

# ──────────────────────────────────────────────
# Memory templates per student archetype
# ──────────────────────────────────────────────

def _memories_amira():
    """High-engagement, strong student."""
    return [
        ("interaction", "Asked about the difference between INNER JOIN and LEFT JOIN in SQL. Was able to explain INNER JOIN but wanted clarity on when LEFT JOIN returns NULLs.", ["SQL", "joins", "INNER JOIN", "LEFT JOIN", "NULL values"], "confident", 0.12),
        ("breakthrough", "Had an aha moment understanding how GROUP BY and aggregate functions work together. Connected it to the concept of map-reduce from the readings.", ["SQL", "GROUP BY", "aggregate functions", "map-reduce"], "confident", 0.05),
        ("question", "Why do we need to normalize databases? Wouldn't it be simpler to keep everything in one big table?", ["database normalization", "database design", "SQL"], "neutral", 0.20),
        ("insight", "Realized that Python list comprehensions are essentially a compact form of a for-loop with an optional filter, similar to SQL SELECT with WHERE.", ["list comprehensions", "loops", "SQL", "SELECT", "WHERE clause"], "confident", 0.08),
        ("interaction", "Worked through a complex nested loop problem involving 2D arrays. Traced through execution step by step and got correct output.", ["nested loops", "2D arrays", "arrays", "debugging"], "confident", 0.10),
        ("struggle", "Got confused by variable scope inside nested functions. A variable defined in the outer function was accessible in the inner one but not vice versa.", ["variable scope", "functions", "nested functions", "closures"], "confused", 0.35),
        ("breakthrough", "Finally understood recursion by visualizing the call stack. The factorial example clicked when I drew the stack frames on paper.", ["recursion", "call stack", "functions", "factorial"], "confident", 0.05),
        ("question", "How do database indexes work under the hood? Are they like binary search trees?", ["database indexes", "binary search trees", "SQL", "query optimization"], "neutral", 0.15),
        ("interaction", "Completed the SQL subquery assignment with no issues. Used correlated subqueries to find students with above-average grades per department.", ["SQL", "subqueries", "correlated subqueries", "aggregate functions"], "confident", 0.08),
        ("insight", "The relationship between Python dictionaries and database hash indexes clicked. Both use key-value lookup for O(1) access.", ["dictionaries", "hash tables", "database indexes", "data structures"], "confident", 0.05),
        ("interaction", "Reviewed sorting algorithms and explained to a peer why quicksort is O(n log n) on average but O(n^2) worst case.", ["sorting algorithms", "quicksort", "time complexity", "algorithms"], "confident", 0.10),
        ("question", "Can you have a foreign key that references a composite primary key? How would that work in SQL?", ["foreign keys", "composite keys", "SQL", "database design"], "neutral", 0.18),
    ]


def _memories_jordan():
    """High-engagement, good student with some SQL gaps."""
    return [
        ("interaction", "Worked through while-loop exercises. Understood the pattern but initially forgot to update the loop variable, causing an infinite loop.", ["while loops", "loops", "infinite loops", "debugging"], "neutral", 0.20),
        ("struggle", "SQL JOINs are really confusing. I keep mixing up which table goes on the left vs right side of the JOIN and when NULLs appear.", ["SQL", "joins", "LEFT JOIN", "RIGHT JOIN", "NULL values"], "frustrated", 0.55),
        ("breakthrough", "Figured out that for-each loops in Python are actually iterating over an iterator object. The iter() and next() connection clicked.", ["for loops", "iterators", "loops", "Python internals"], "confident", 0.10),
        ("question", "What's the difference between a function that returns a value and one that modifies a list in place? When should I use which?", ["functions", "return values", "mutability", "lists"], "neutral", 0.25),
        ("interaction", "Wrote a function to reverse a string using a loop. Then refactored it using slicing. Discussed trade-offs of readability vs conciseness.", ["functions", "strings", "loops", "string slicing", "code style"], "confident", 0.12),
        ("struggle", "SQL subqueries still don't make sense. Why would I write a query inside another query instead of just doing two separate queries?", ["SQL", "subqueries", "query design"], "frustrated", 0.60),
        ("insight", "Arrays in Python (lists) are dynamic because they use an underlying array that doubles in size. That's why append is amortized O(1).", ["arrays", "lists", "dynamic arrays", "amortized analysis", "data structures"], "confident", 0.08),
        ("interaction", "Practiced writing conditional statements with nested if-elif-else. Got tripped up by operator precedence with 'and' vs 'or'.", ["conditionals", "boolean logic", "operator precedence", "if-else"], "neutral", 0.22),
        ("question", "In SQL, what's the difference between WHERE and HAVING? They both filter rows, right?", ["SQL", "WHERE clause", "HAVING", "GROUP BY", "aggregate functions"], "confused", 0.40),
        ("breakthrough", "Finally understood how SQL JOINs work by thinking of them as nested loops that match rows based on a condition. Drew a Venn diagram.", ["SQL", "joins", "INNER JOIN", "mental models"], "confident", 0.12),
        ("interaction", "Completed the functions lab. Wrote helper functions for input validation and learned about the DRY principle.", ["functions", "input validation", "DRY principle", "code quality"], "confident", 0.10),
    ]


def _memories_priya():
    """Medium-engagement, frequently confused."""
    return [
        ("struggle", "I don't understand why x = 5 and then x = 'hello' is allowed in Python. Doesn't x already have a type? This is really confusing.", ["variables", "data types", "dynamic typing", "type system"], "confused", 0.70),
        ("question", "What's the difference between an integer and a float? When would I use 5 vs 5.0?", ["data types", "integers", "floats", "numeric types"], "confused", 0.55),
        ("struggle", "I wrote a for loop but it only printed the last element. I think I had the print outside the loop body. Indentation is tricky.", ["for loops", "loops", "indentation", "syntax errors"], "frustrated", 0.65),
        ("interaction", "Went through basic variable assignment exercises. Starting to understand that variables are like labels that point to values.", ["variables", "assignment", "mental models"], "neutral", 0.40),
        ("question", "Why do arrays start at index 0 instead of 1? It doesn't make intuitive sense to me.", ["arrays", "indexing", "zero-based indexing"], "confused", 0.45),
        ("breakthrough", "I finally get if-else statements! It's like a fork in the road -- you check the condition and go one way or the other.", ["conditionals", "if-else", "control flow"], "confident", 0.15),
        ("struggle", "SQL SELECT statements are overwhelming. There are so many clauses -- FROM, WHERE, ORDER BY, LIMIT. I don't know what order they go in.", ["SQL", "SELECT", "query syntax", "SQL clauses"], "frustrated", 0.72),
        ("interaction", "Practiced converting between data types: int(), str(), float(). Made mistakes with int('hello') and now understand why it raises an error.", ["data types", "type conversion", "casting", "error handling"], "neutral", 0.38),
        ("question", "What does 'return' do in a function? How is it different from 'print'?", ["functions", "return values", "print", "output"], "confused", 0.50),
        ("insight", "I think I understand loops now -- a while loop is like asking 'are we there yet?' over and over until the answer is yes.", ["while loops", "loops", "mental models", "control flow"], "neutral", 0.30),
        ("struggle", "Tried to write a function that takes a list and returns the average but kept getting a TypeError. Turns out I was dividing a list by a number.", ["functions", "lists", "TypeError", "debugging", "arithmetic"], "frustrated", 0.68),
    ]


def _memories_marcus():
    """Medium-engagement, strong on arrays/loops, weak on SQL."""
    return [
        ("interaction", "Completed the array manipulation exercises quickly. Sorted, filtered, and mapped over arrays without issues.", ["arrays", "sorting", "filtering", "array methods"], "confident", 0.10),
        ("breakthrough", "Understood how to use nested loops to iterate over 2D arrays. Rows are the outer loop, columns are the inner loop.", ["nested loops", "2D arrays", "arrays", "loops"], "confident", 0.08),
        ("struggle", "I cannot wrap my head around SQL joins. Tried to join three tables and got way more rows than expected. What is a Cartesian product?", ["SQL", "joins", "Cartesian product", "multi-table queries"], "frustrated", 0.65),
        ("question", "How do you decide when to use a for loop vs a while loop? Is there a rule of thumb?", ["for loops", "while loops", "loops", "control flow"], "neutral", 0.20),
        ("interaction", "Wrote a binary search function for a sorted array. Understood the O(log n) time complexity by thinking about halving the search space.", ["binary search", "arrays", "algorithms", "time complexity", "sorting"], "confident", 0.12),
        ("struggle", "Database normalization makes no sense to me. Why would I split one table into three? It seems like more work for no benefit.", ["database normalization", "database design", "SQL", "relational databases"], "frustrated", 0.58),
        ("interaction", "Practiced defining and calling functions with multiple parameters. Learned about default parameter values.", ["functions", "parameters", "default values"], "neutral", 0.18),
        ("question", "What's the point of using a dictionary when I could just use two parallel arrays -- one for keys and one for values?", ["dictionaries", "arrays", "data structures", "key-value pairs"], "neutral", 0.25),
        ("struggle", "Tried to write a SQL query with GROUP BY but kept getting errors about non-aggregated columns in the SELECT.", ["SQL", "GROUP BY", "aggregate functions", "query errors"], "confused", 0.55),
        ("insight", "The connection between Python loops and SQL -- a SELECT with WHERE is basically a loop that filters. SQL just does it declaratively.", ["SQL", "loops", "declarative programming", "mental models"], "neutral", 0.20),
    ]


def _memories_elena():
    """Top performer, advanced topics."""
    return [
        ("interaction", "Explored window functions in SQL (ROW_NUMBER, RANK, LAG). Used them to compute running totals and compare consecutive rows.", ["SQL", "window functions", "ROW_NUMBER", "aggregate functions", "advanced SQL"], "confident", 0.05),
        ("breakthrough", "Realized that recursion and mathematical induction follow the same structure: base case + inductive step = recursive case + base case.", ["recursion", "mathematical induction", "functions", "algorithms"], "confident", 0.03),
        ("interaction", "Implemented a hash table from scratch using chaining for collision resolution. Understood load factor and rehashing.", ["hash tables", "data structures", "collision resolution", "implementation"], "confident", 0.08),
        ("insight", "SQL query execution order (FROM -> WHERE -> GROUP BY -> HAVING -> SELECT -> ORDER BY) explains why you can't use column aliases in WHERE.", ["SQL", "query execution order", "SQL clauses", "column aliases"], "confident", 0.05),
        ("question", "Is there a way to have recursive SQL queries? Like finding all ancestors in a hierarchy?", ["SQL", "recursive queries", "CTEs", "hierarchical data"], "neutral", 0.12),
        ("interaction", "Wrote a merge sort implementation and analyzed its O(n log n) time and O(n) space complexity. Compared it to quicksort's in-place advantage.", ["sorting algorithms", "merge sort", "quicksort", "time complexity", "space complexity"], "confident", 0.06),
        ("breakthrough", "The concept of closures finally clicked -- a function remembers the environment where it was created, even after that scope exits.", ["closures", "functions", "variable scope", "nested functions"], "confident", 0.04),
        ("interaction", "Helped two classmates understand how foreign keys enforce referential integrity. Used a library-books analogy.", ["foreign keys", "referential integrity", "database design", "SQL"], "confident", 0.05),
        ("insight", "Python's list.sort() uses Timsort, which is a hybrid of merge sort and insertion sort. It's O(n) on nearly-sorted data.", ["sorting algorithms", "Timsort", "Python internals", "time complexity"], "confident", 0.03),
        ("question", "How do database transactions and ACID properties work? What happens if two users update the same row simultaneously?", ["database transactions", "ACID", "concurrency", "SQL", "isolation levels"], "neutral", 0.15),
        ("interaction", "Created a linked list class with insert, delete, and search methods. Compared performance characteristics with Python lists (arrays).", ["linked lists", "data structures", "arrays", "time complexity"], "confident", 0.07),
        ("insight", "Functional programming concepts like map/filter/reduce directly correspond to SQL operations: SELECT (map), WHERE (filter), GROUP BY+AGG (reduce).", ["functional programming", "SQL", "map", "filter", "reduce", "aggregate functions"], "confident", 0.04),
        ("interaction", "Investigated how SQL indexes use B-trees for range queries and hash indexes for equality lookups. Drew the B-tree structure.", ["database indexes", "B-trees", "hash indexes", "SQL", "query optimization"], "confident", 0.06),
        ("question", "What are the trade-offs of using an ORM vs raw SQL? When is each approach better?", ["SQL", "ORM", "database design", "software engineering"], "neutral", 0.10),
        ("breakthrough", "Connected the concept of SQL views to functions in programming -- both are named abstractions that encapsulate a computation.", ["SQL", "views", "functions", "abstraction", "mental models"], "confident", 0.05),
    ]


def _memories_tyler():
    """Low-engagement, persistently confused."""
    return [
        ("struggle", "I don't know what a variable is. Is it like a box? The teacher said it's a name that refers to a value but that doesn't help.", ["variables", "assignment", "mental models"], "confused", 0.80),
        ("question", "What does = mean in code? It's not the same as math equals, right?", ["variables", "assignment", "operators"], "confused", 0.75),
        ("struggle", "Tried to run my code but got a SyntaxError. I don't understand what a syntax error is or how to fix it.", ["syntax errors", "debugging", "error messages"], "frustrated", 0.82),
        ("interaction", "Went through the very basics of data types: int, float, str, bool. Still not clear on why it matters what type something is.", ["data types", "integers", "floats", "strings", "booleans"], "confused", 0.70),
        ("struggle", "I wrote 'if x = 5' and got an error. Apparently it should be 'if x == 5'. Why are there two different equals signs?", ["conditionals", "operators", "assignment", "comparison operators", "syntax errors"], "frustrated", 0.78),
    ]


def _memories_sophia():
    """Medium-engagement, strong on conditionals, struggles with SQL."""
    return [
        ("interaction", "Completed the conditionals worksheet with perfect score. Nested if-elif-else chains make sense to me now.", ["conditionals", "if-else", "nested conditionals", "control flow"], "confident", 0.10),
        ("breakthrough", "Realized that boolean expressions can be combined with and/or/not just like in everyday language. 'Is it raining AND cold?' translates directly.", ["boolean logic", "conditionals", "operators", "and", "or", "not"], "confident", 0.08),
        ("struggle", "SQL is like a foreign language. I wrote SELECT name WHERE grade > 90 and it said I need a FROM clause. Why isn't it obvious?", ["SQL", "SELECT", "FROM clause", "query syntax"], "frustrated", 0.65),
        ("question", "What's the difference between a list and a tuple? My textbook says tuples are immutable but I don't know why that matters.", ["lists", "tuples", "mutability", "data structures"], "confused", 0.40),
        ("interaction", "Practiced writing for loops to iterate over lists. Got comfortable with the range() function and its start/stop/step parameters.", ["for loops", "loops", "range function", "lists"], "neutral", 0.20),
        ("struggle", "Tried to do SQL GROUP BY with a WHERE clause on the aggregated result. Apparently I need HAVING, not WHERE. The distinction is so arbitrary.", ["SQL", "GROUP BY", "WHERE clause", "HAVING", "aggregate functions"], "frustrated", 0.70),
        ("question", "What happens if you call a function inside itself? Does the program crash or does it actually work?", ["recursion", "functions", "call stack"], "neutral", 0.35),
        ("interaction", "Wrote a function that takes a list of numbers and returns only the even ones using a loop and conditional. It worked on the first try!", ["functions", "loops", "conditionals", "lists", "filtering"], "confident", 0.12),
        ("struggle", "SQL JOINs are impossible. I don't understand why I'd combine two tables. Can't I just look at them separately?", ["SQL", "joins", "relational databases", "multi-table queries"], "frustrated", 0.72),
        ("insight", "Conditionals in code are like Excel IF() formulas. If this condition is true do one thing, otherwise do another. That analogy really helps me.", ["conditionals", "if-else", "mental models", "analogies"], "confident", 0.10),
    ]


def _memories_david():
    """Inactive, deeply confused on everything."""
    return [
        ("struggle", "I have no idea what I'm doing. The whole class has moved on to functions and I still don't understand how loops work.", ["loops", "functions", "falling behind"], "frustrated", 0.90),
        ("question", "What is Python? Is it the same as the thing we type code into?", ["Python", "programming basics", "IDE"], "confused", 0.85),
        ("struggle", "Tried to do the first assignment but couldn't even open the file. I don't know what a .py file is.", ["file management", "Python basics", "getting started"], "frustrated", 0.88),
        ("interaction", "Briefly looked at the data types lesson. I think I understand that numbers and text are different types but I'm not sure why that matters.", ["data types", "integers", "strings"], "confused", 0.75),
        ("struggle", "Everyone else seems to understand loops and I'm completely lost. I don't even know what 'iterate' means.", ["loops", "iteration", "falling behind", "vocabulary"], "frustrated", 0.92),
    ]


MEMORY_GENERATORS = [
    _memories_amira,
    _memories_jordan,
    _memories_priya,
    _memories_marcus,
    _memories_elena,
    _memories_tyler,
    _memories_sophia,
    _memories_david,
]


async def main():
    conn = await asyncpg.connect(DB_DSN)

    try:
        # ── 1. Create Users ────────────────────────────
        student_ids: list[uuid.UUID] = []
        now = datetime.now(timezone.utc)

        print("Creating students...")
        for s in STUDENTS:
            sid = uuid.uuid4()
            student_ids.append(sid)

            await conn.execute(
                """
                INSERT INTO users (id, name, email, role, created_at, updated_at)
                VALUES ($1, $2, $3, 'student', $4, $4)
                ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                sid,
                s["name"],
                s["email"],
                now,
            )
            print(f"  + {s['name']} ({sid})")

        # ── 2. Create Enrollments ──────────────────────
        print("\nCreating enrollments...")
        for i, sid in enumerate(student_ids):
            eid = uuid.uuid4()
            enrolled_at = now - timedelta(days=random.randint(30, 90))
            await conn.execute(
                """
                INSERT INTO enrollments (id, user_id, course_id, lms_role, enrolled_at)
                VALUES ($1, $2, $3, 'student', $4)
                ON CONFLICT ON CONSTRAINT uq_enrollment DO NOTHING
                """,
                eid,
                sid,
                COURSE_ID,
                enrolled_at,
            )
            print(f"  + Enrolled {STUDENTS[i]['name']}")

        # ── 3. Create StudentProfiles ──────────────────
        print("\nCreating student profiles...")
        for i, sid in enumerate(student_ids):
            s = STUDENTS[i]
            pid = uuid.uuid4()

            # Determine last_interaction_at based on engagement
            if s["engagement"] == "inactive":
                last_interaction = now - timedelta(days=random.randint(21, 35))
            elif s["engagement"] == "low":
                last_interaction = now - timedelta(days=random.randint(5, 12))
            elif s["engagement"] == "medium":
                last_interaction = now - timedelta(days=random.randint(1, 4))
            else:  # high
                last_interaction = now - timedelta(hours=random.randint(1, 36))

            preferred_times = {
                "morning": round(random.uniform(0.1, 0.4), 2),
                "afternoon": round(random.uniform(0.2, 0.5), 2),
                "evening": round(random.uniform(0.1, 0.5), 2),
                "night": round(random.uniform(0.0, 0.2), 2),
            }
            # Normalize so they sum to ~1
            total = sum(preferred_times.values())
            preferred_times = {k: round(v / total, 2) for k, v in preferred_times.items()}

            await conn.execute(
                """
                INSERT INTO student_profiles
                    (id, student_id, course_id, total_interactions, total_messages,
                     avg_confusion_score, avg_interaction_score, engagement_level,
                     current_grade, last_interaction_at, avg_session_duration_minutes,
                     preferred_interaction_times, profile_summary, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                ON CONFLICT ON CONSTRAINT uq_student_profile DO UPDATE SET
                    total_interactions = EXCLUDED.total_interactions,
                    total_messages = EXCLUDED.total_messages,
                    avg_confusion_score = EXCLUDED.avg_confusion_score,
                    avg_interaction_score = EXCLUDED.avg_interaction_score,
                    engagement_level = EXCLUDED.engagement_level,
                    current_grade = EXCLUDED.current_grade,
                    last_interaction_at = EXCLUDED.last_interaction_at,
                    avg_session_duration_minutes = EXCLUDED.avg_session_duration_minutes,
                    preferred_interaction_times = EXCLUDED.preferred_interaction_times,
                    profile_summary = EXCLUDED.profile_summary,
                    updated_at = EXCLUDED.updated_at
                """,
                pid,
                sid,
                COURSE_ID,
                s["total_interactions"],
                s["total_messages"],
                s["confusion_avg"],
                s["interaction_score_avg"],
                s["engagement"],
                s["grade"],
                last_interaction,
                s["session_duration"],
                json.dumps(preferred_times),
                s["summary"],
                now,
            )
            print(f"  + Profile for {s['name']} (engagement={s['engagement']}, grade={s['grade']})")

        # ── 4. Create MemoryRecords ────────────────────
        print("\nCreating memory records...")
        total_memories = 0
        for i, sid in enumerate(student_ids):
            memories = MEMORY_GENERATORS[i]()
            s = STUDENTS[i]
            print(f"  {s['name']}: {len(memories)} memories")

            for memory_type, content, concepts, sentiment, confusion in memories:
                mid = uuid.uuid4()
                # Spread memories over the past 30-60 days
                created_at = now - timedelta(
                    days=random.randint(1, 60),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                )
                metadata = json.dumps({
                    "topic_week": random.randint(1, 14),
                    "interaction_duration_seconds": random.randint(30, 600),
                })

                await conn.execute(
                    """
                    INSERT INTO memory_records
                        (id, student_id, course_id, memory_type, content,
                         concepts, sentiment, confusion_score, source,
                         metadata, is_compressed, created_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                    """,
                    mid,
                    sid,
                    COURSE_ID,
                    memory_type,
                    content,
                    concepts,
                    sentiment,
                    confusion,
                    "mock_injection",
                    metadata,
                    False,
                    created_at,
                )
                total_memories += 1

        print(f"\nTotal memory records created: {total_memories}")

        # ── 5. Summary ─────────────────────────────────
        user_count = await conn.fetchval(
            "SELECT count(*) FROM users WHERE email LIKE '%@university.edu'"
        )
        enrollment_count = await conn.fetchval(
            "SELECT count(*) FROM enrollments WHERE course_id = $1", COURSE_ID
        )
        profile_count = await conn.fetchval(
            "SELECT count(*) FROM student_profiles WHERE course_id = $1", COURSE_ID
        )
        memory_count = await conn.fetchval(
            "SELECT count(*) FROM memory_records WHERE course_id = $1 AND source = 'mock_injection'",
            COURSE_ID,
        )

        print("\n" + "=" * 50)
        print("INJECTION COMPLETE")
        print("=" * 50)
        print(f"  Students created:      {user_count}")
        print(f"  Enrollments:           {enrollment_count}")
        print(f"  Student profiles:      {profile_count}")
        print(f"  Memory records:        {memory_count}")
        print(f"  Course ID:             {COURSE_ID}")

        # Show concept overlap
        concept_rows = await conn.fetch(
            """
            SELECT unnest(concepts) AS concept, count(DISTINCT student_id) AS student_count
            FROM memory_records
            WHERE course_id = $1 AND source = 'mock_injection'
            GROUP BY concept
            HAVING count(DISTINCT student_id) >= 2
            ORDER BY student_count DESC, concept
            LIMIT 20
            """,
            COURSE_ID,
        )
        print(f"\n  Top shared concepts (appearing in 2+ students):")
        for row in concept_rows:
            print(f"    {row['concept']:30s}  ({row['student_count']} students)")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
