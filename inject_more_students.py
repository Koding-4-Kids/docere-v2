"""
Inject 10 MORE mock students into the Docere database for course 5273900d-c97c-41d2-95fe-af51e9b8ac41.

Adds to the existing 8 mock students + 1 real student:
- 10 new students with diverse backgrounds
- Mix of engagement levels (high, medium, low)
- StudentProfile records with varying stats
- 5-12 MemoryRecord entries each with realistic CS content
- Varied memory types, concepts, sentiments, and confusion scores
- All memories tagged with source = 'mock_injection'
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
# 10 New Student Personas
# ──────────────────────────────────────────────
STUDENTS = [
    {
        "name": "Fatima Al-Rashid",
        "email": "fatima.alrashid@university.edu",
        "engagement": "high",
        "grade": 90.0,
        "confusion_avg": 0.18,
        "interaction_score_avg": 0.85,
        "total_interactions": 44,
        "total_messages": 121,
        "session_duration": 35.0,
        "summary": "Diligent student with strong fundamentals in loops and conditionals. Recently making breakthroughs in OOP concepts. Asks precise, targeted questions and revisits previous material to reinforce understanding.",
    },
    {
        "name": "Liam O'Sullivan",
        "email": "liam.osullivan@university.edu",
        "engagement": "medium",
        "grade": 76.0,
        "confusion_avg": 0.42,
        "interaction_score_avg": 0.59,
        "total_interactions": 22,
        "total_messages": 58,
        "session_duration": 20.0,
        "summary": "Inconsistent engagement -- comes in bursts around deadlines. Decent grasp of arrays and basic sorting but struggles with recursion and inheritance. Needs motivation to stay consistent.",
    },
    {
        "name": "Mei-Ling Chen",
        "email": "meiling.chen@university.edu",
        "engagement": "high",
        "grade": 94.0,
        "confusion_avg": 0.12,
        "interaction_score_avg": 0.91,
        "total_interactions": 50,
        "total_messages": 145,
        "session_duration": 40.0,
        "summary": "Exceptional problem-solver who quickly connects new concepts to prior knowledge. Strong in algorithms, data structures, and SQL. Proactively explores recursion and OOP patterns beyond assignments.",
    },
    {
        "name": "Carlos Gutierrez",
        "email": "carlos.gutierrez@university.edu",
        "engagement": "low",
        "grade": 62.0,
        "confusion_avg": 0.58,
        "interaction_score_avg": 0.35,
        "total_interactions": 13,
        "total_messages": 31,
        "session_duration": 14.0,
        "summary": "Low engagement with sporadic interactions. Has fundamental gaps in understanding variables and data types. Shows flashes of insight on conditionals but rarely follows through on practice exercises.",
    },
    {
        "name": "Anya Petrov",
        "email": "anya.petrov@university.edu",
        "engagement": "medium",
        "grade": 80.0,
        "confusion_avg": 0.38,
        "interaction_score_avg": 0.65,
        "total_interactions": 26,
        "total_messages": 72,
        "session_duration": 24.0,
        "summary": "Solid middle-of-the-pack student. Comfortable with functions and basic debugging but confused by pointers and memory concepts. Responds well to visual explanations and diagrams.",
    },
    {
        "name": "Kwame Asante",
        "email": "kwame.asante@university.edu",
        "engagement": "high",
        "grade": 87.0,
        "confusion_avg": 0.20,
        "interaction_score_avg": 0.80,
        "total_interactions": 41,
        "total_messages": 110,
        "session_duration": 33.0,
        "summary": "Curious and persistent learner. Excels in debugging and algorithms. Actively working through OOP concepts and class inheritance. Prefers learning through building projects rather than reading.",
    },
    {
        "name": "Isabella Ferreira",
        "email": "isabella.ferreira@university.edu",
        "engagement": "medium",
        "grade": 73.0,
        "confusion_avg": 0.48,
        "interaction_score_avg": 0.52,
        "total_interactions": 18,
        "total_messages": 48,
        "session_duration": 17.0,
        "summary": "Engaged during lectures but struggles to apply concepts independently. Has difficulty with SQL joins and GROUP BY. Benefits greatly from worked examples and pair programming analogies.",
    },
    {
        "name": "Raj Patel",
        "email": "raj.patel@university.edu",
        "engagement": "low",
        "grade": 68.0,
        "confusion_avg": 0.55,
        "interaction_score_avg": 0.40,
        "total_interactions": 15,
        "total_messages": 37,
        "session_duration": 15.0,
        "summary": "Capable but underprepared student who entered without prior programming experience. Making slow progress on loops and conditionals. Frequently confused by sorting algorithms and recursion.",
    },
    {
        "name": "Suki Tanaka",
        "email": "suki.tanaka@university.edu",
        "engagement": "high",
        "grade": 91.0,
        "confusion_avg": 0.14,
        "interaction_score_avg": 0.87,
        "total_interactions": 46,
        "total_messages": 128,
        "session_duration": 37.0,
        "summary": "Highly motivated student with strong analytical skills. Deep understanding of data structures and algorithms. Currently mastering OOP design patterns and advanced SQL. Helps classmates regularly.",
    },
    {
        "name": "Oluwaseun Adeyemi",
        "email": "oluwaseun.adeyemi@university.edu",
        "engagement": "medium",
        "grade": 77.0,
        "confusion_avg": 0.40,
        "interaction_score_avg": 0.62,
        "total_interactions": 24,
        "total_messages": 65,
        "session_duration": 21.0,
        "summary": "Steady learner who shows strong effort on assignments. Good intuition for conditionals and loops but needs more practice with classes, inheritance, and pointer concepts. Improving week over week.",
    },
]

# ──────────────────────────────────────────────
# Memory templates per student
# ──────────────────────────────────────────────

def _memories_fatima():
    """High-engagement, strong fundamentals, breaking into OOP."""
    return [
        ("interaction", "Worked through all loop exercises including nested loops for matrix traversal. Had no issues with for-loops but needed a hint on while-loop termination conditions.", ["loops", "nested loops", "while loops", "arrays"], "confident", 0.12),
        ("breakthrough", "OOP finally clicked when I realized a class is just a blueprint and an object is a house built from that blueprint. The __init__ method sets up each house differently.", ["OOP", "classes", "objects", "constructors", "__init__"], "confident", 0.06),
        ("question", "How does inheritance work when a child class needs to override only part of a parent method? Do I have to rewrite the whole thing?", ["inheritance", "OOP", "method overriding", "classes"], "neutral", 0.22),
        ("insight", "SQL GROUP BY is like sorting your laundry into piles by color, then counting each pile. The aggregate function is the counting step.", ["SQL", "GROUP BY", "aggregate functions", "mental models"], "confident", 0.08),
        ("interaction", "Implemented a Student class with attributes for name, grades, and a method to compute GPA. Extended it to GraduateStudent with a thesis attribute.", ["OOP", "classes", "inheritance", "methods", "attributes"], "confident", 0.10),
        ("struggle", "Got confused by the difference between class variables and instance variables. Changed a class variable thinking it would only affect one object, but it changed for all of them.", ["OOP", "classes", "class variables", "instance variables", "scope"], "confused", 0.35),
        ("question", "When should I use a list vs a dictionary vs a set? Is there a decision tree for choosing the right data structure?", ["data structures", "lists", "dictionaries", "sets", "design decisions"], "neutral", 0.18),
        ("interaction", "Completed the SQL joins assignment. Used INNER JOIN and LEFT JOIN correctly. Drew table diagrams to verify my results matched expected output.", ["SQL", "joins", "INNER JOIN", "LEFT JOIN", "debugging"], "confident", 0.10),
        ("breakthrough", "Realized that recursion on trees is natural because each subtree is itself a tree. The base case is when you hit a leaf node with no children.", ["recursion", "data structures", "trees", "base case"], "confident", 0.05),
        ("insight", "Sorting algorithms trade off between time complexity and space complexity. Merge sort uses extra space but guarantees O(n log n). Insertion sort is in-place but O(n^2).", ["sorting", "algorithms", "time complexity", "merge sort", "insertion sort"], "confident", 0.08),
    ]


def _memories_liam():
    """Medium-engagement, burst learner, struggles with recursion."""
    return [
        ("interaction", "Rushed through the arrays assignment before the deadline. Got most of it right but made off-by-one errors on index calculations.", ["arrays", "indexing", "off-by-one errors", "debugging"], "neutral", 0.25),
        ("struggle", "Recursion is black magic. I tried to trace through a recursive Fibonacci function and got completely lost after the third call. How does the computer keep track of all these calls?", ["recursion", "Fibonacci", "call stack", "functions"], "frustrated", 0.65),
        ("question", "Why can't I just use loops for everything? What does recursion give me that loops don't?", ["recursion", "loops", "iteration vs recursion", "algorithms"], "frustrated", 0.50),
        ("interaction", "Sorted an array using bubble sort. It worked but the TA said it's O(n^2). I need to understand what that means practically.", ["sorting", "bubble sort", "time complexity", "algorithms"], "neutral", 0.30),
        ("struggle", "Inheritance is confusing. If Dog extends Animal, does Dog get all of Animal's methods automatically? What if I want to change one?", ["inheritance", "OOP", "classes", "method overriding"], "confused", 0.55),
        ("breakthrough", "Finally understood how array slicing works in Python. arr[1:4] gives elements at indices 1, 2, 3 -- not 4. It's like a half-open interval.", ["arrays", "slicing", "indexing", "Python"], "confident", 0.10),
        ("question", "What's the difference between a shallow copy and a deep copy of a list? My function was accidentally modifying the original list.", ["lists", "copying", "shallow copy", "deep copy", "mutability"], "confused", 0.45),
        ("interaction", "Tried the SQL practice problems. Got basic SELECT and WHERE correct but made errors on JOINs between three tables.", ["SQL", "SELECT", "WHERE clause", "joins", "multi-table queries"], "neutral", 0.35),
    ]


def _memories_meiling():
    """High-engagement, top performer, advanced topics."""
    return [
        ("interaction", "Implemented a binary search tree with insert, search, and in-order traversal. Analyzed why search is O(log n) for balanced trees but O(n) for degenerate ones.", ["data structures", "binary search trees", "algorithms", "time complexity", "trees"], "confident", 0.05),
        ("breakthrough", "Polymorphism means I can write code that works on any object that follows a certain interface, without knowing the specific class. Duck typing in Python makes this natural.", ["OOP", "polymorphism", "interfaces", "duck typing", "classes"], "confident", 0.04),
        ("insight", "Recursive algorithms on data structures mirror the structure of the data itself. Traversing a tree recursively works because a tree is defined recursively.", ["recursion", "data structures", "trees", "algorithms", "structural recursion"], "confident", 0.03),
        ("interaction", "Wrote SQL queries using CTEs (Common Table Expressions) to break complex queries into readable steps. Much cleaner than nested subqueries.", ["SQL", "CTEs", "subqueries", "query design", "readability"], "confident", 0.06),
        ("question", "How do hash collisions affect performance in Python dictionaries? Is there a worst case where lookup degrades to O(n)?", ["data structures", "hash tables", "dictionaries", "collision resolution", "time complexity"], "neutral", 0.12),
        ("interaction", "Designed a class hierarchy for a shape calculator: Shape -> Rectangle, Circle, Triangle. Each subclass implements its own area() and perimeter() methods.", ["OOP", "classes", "inheritance", "polymorphism", "method overriding"], "confident", 0.05),
        ("breakthrough", "The connection between recursion and the call stack became crystal clear when I visualized it as a stack of plates. Each recursive call adds a plate, and each return removes one.", ["recursion", "call stack", "stack data structure", "visualization"], "confident", 0.03),
        ("insight", "SQL window functions let you compute aggregates without collapsing rows, unlike GROUP BY. PARTITION BY is like GROUP BY but keeps all original rows.", ["SQL", "window functions", "GROUP BY", "PARTITION BY", "aggregate functions"], "confident", 0.05),
        ("interaction", "Implemented quicksort with both Lomuto and Hoare partition schemes. Benchmarked them on random vs nearly-sorted data to see the performance difference.", ["sorting", "quicksort", "algorithms", "partitioning", "benchmarking"], "confident", 0.06),
        ("question", "What are design patterns like Singleton and Factory? When would I use them in a real project?", ["OOP", "design patterns", "Singleton", "Factory", "software engineering"], "neutral", 0.10),
        ("interaction", "Helped a classmate debug a recursive function that was hitting maximum recursion depth. The base case was wrong -- it never stopped calling itself.", ["recursion", "debugging", "base case", "stack overflow", "functions"], "confident", 0.04),
        ("insight", "Pointers in C are just memory addresses. Dereferencing a pointer is like following a treasure map to find the actual treasure (the value stored at that address).", ["pointers", "memory", "C programming", "mental models"], "confident", 0.05),
    ]


def _memories_carlos():
    """Low-engagement, fundamental gaps."""
    return [
        ("struggle", "I keep mixing up = and ==. I wrote if grade = 90 and Python yelled at me. Apparently = is for setting a value and == is for checking.", ["variables", "assignment", "comparison operators", "conditionals", "syntax errors"], "frustrated", 0.65),
        ("question", "What's a function? My friend said it's like a recipe but I still don't understand how def and return work together.", ["functions", "return values", "def keyword", "programming basics"], "confused", 0.55),
        ("interaction", "Went through the conditionals tutorial. I can write basic if-else statements now but nested ones still trip me up.", ["conditionals", "if-else", "nested conditionals", "control flow"], "neutral", 0.40),
        ("struggle", "Tried to write a loop that counts from 1 to 10. Got an infinite loop because I forgot to increment the counter. Had to force-quit the program.", ["loops", "while loops", "infinite loops", "debugging"], "frustrated", 0.70),
        ("question", "Why does Python care about indentation? Other things I've seen online don't seem to need it. It keeps breaking my code.", ["indentation", "syntax errors", "Python", "code structure"], "frustrated", 0.60),
        ("insight", "I think I'm starting to get variables. x = 5 means 'x now holds 5'. If I later say x = 10, it just holds 10 now. The old value is gone.", ["variables", "assignment", "data types", "mental models"], "neutral", 0.35),
        ("struggle", "Data types are confusing. I tried to add a number to a string with '5' + 3 and got a TypeError. Why can't Python just figure out what I mean?", ["data types", "type errors", "strings", "integers", "type conversion"], "frustrated", 0.62),
    ]


def _memories_anya():
    """Medium-engagement, solid on functions, confused by pointers/memory."""
    return [
        ("interaction", "Completed the functions lab with all test cases passing. Wrote helper functions for input validation and string formatting.", ["functions", "input validation", "strings", "testing"], "confident", 0.12),
        ("breakthrough", "Debugging became much easier once I learned to use print statements to trace variable values at each step. It's like leaving breadcrumbs.", ["debugging", "print statements", "tracing", "variables"], "confident", 0.08),
        ("struggle", "Pointers and references make no sense to me. Why would I want to work with the address of something instead of the thing itself?", ["pointers", "references", "memory", "indirection"], "confused", 0.60),
        ("question", "What's the difference between passing by value and passing by reference? My function changed the original list when I didn't want it to.", ["functions", "pass by value", "pass by reference", "mutability", "lists"], "confused", 0.45),
        ("interaction", "Wrote a function to check if a string is a palindrome using a loop. Then rewrote it using recursion -- the recursive version was shorter but harder to understand.", ["functions", "recursion", "strings", "loops", "palindromes"], "neutral", 0.22),
        ("struggle", "Memory allocation diagrams are overwhelming. Stack vs heap, local variables vs dynamically allocated objects -- I can't keep it all straight.", ["memory", "stack", "heap", "pointers", "allocation"], "frustrated", 0.58),
        ("insight", "Arrays store elements contiguously in memory, which is why indexing is O(1) -- you just calculate the offset from the start address.", ["arrays", "memory", "indexing", "time complexity", "data structures"], "confident", 0.15),
        ("interaction", "Practiced SQL SELECT statements with WHERE, ORDER BY, and LIMIT. Got comfortable with basic queries but haven't tried JOINs yet.", ["SQL", "SELECT", "WHERE clause", "ORDER BY", "LIMIT"], "neutral", 0.20),
        ("question", "In OOP, what's the point of private attributes? If I make something private with an underscore, someone can still access it, right?", ["OOP", "encapsulation", "private attributes", "classes", "access modifiers"], "neutral", 0.30),
    ]


def _memories_kwame():
    """High-engagement, excels at debugging and algorithms, learning OOP."""
    return [
        ("interaction", "Debugged a classmate's sorting function that was producing incorrect output. Found that the swap logic was using a temporary variable incorrectly.", ["debugging", "sorting", "variables", "algorithms"], "confident", 0.08),
        ("breakthrough", "Classes in OOP are like real-world categories. A Car class defines what all cars have (wheels, engine) and can do (drive, brake). Each car object is a specific instance.", ["OOP", "classes", "objects", "abstraction", "mental models"], "confident", 0.06),
        ("interaction", "Implemented selection sort and insertion sort from scratch. Compared their performance on random vs nearly-sorted arrays.", ["sorting", "selection sort", "insertion sort", "algorithms", "benchmarking"], "confident", 0.10),
        ("question", "How does Python garbage collection work? If I delete a variable with del, does the memory get freed immediately?", ["memory", "garbage collection", "Python internals", "variables"], "neutral", 0.20),
        ("struggle", "Multiple inheritance in Python is confusing. If class C inherits from both A and B, and both A and B have a method called greet(), which one does C use?", ["inheritance", "multiple inheritance", "OOP", "MRO", "classes"], "confused", 0.40),
        ("interaction", "Built a simple linked list with append, prepend, and delete methods. Understood how pointer manipulation connects nodes.", ["data structures", "linked lists", "pointers", "algorithms"], "confident", 0.10),
        ("insight", "The DRY principle (Don't Repeat Yourself) is why functions and classes exist -- to package reusable logic so you only write it once.", ["functions", "classes", "DRY principle", "code quality", "software engineering"], "confident", 0.05),
        ("interaction", "Solved SQL problems involving GROUP BY and HAVING. Understood that WHERE filters rows before grouping and HAVING filters groups after.", ["SQL", "GROUP BY", "HAVING", "WHERE clause", "aggregate functions"], "confident", 0.12),
        ("question", "What are abstract classes and when would I use them instead of regular classes?", ["OOP", "abstract classes", "interfaces", "classes", "design patterns"], "neutral", 0.25),
        ("breakthrough", "Realized that a stack is just a list where you only add/remove from one end. The call stack in recursion follows the exact same LIFO principle.", ["data structures", "stacks", "recursion", "call stack", "LIFO"], "confident", 0.05),
    ]


def _memories_isabella():
    """Medium-engagement, struggles with SQL, benefits from examples."""
    return [
        ("interaction", "Followed along with the SQL tutorial and managed basic SELECT and WHERE. But when the instructor moved to JOINs I got lost immediately.", ["SQL", "SELECT", "WHERE clause", "joins"], "neutral", 0.35),
        ("struggle", "SQL GROUP BY is so confusing. I tried to select a column that wasn't in the GROUP BY and got an error. Why can't SQL just figure out which value to show?", ["SQL", "GROUP BY", "aggregate functions", "query errors"], "frustrated", 0.65),
        ("question", "What's the difference between INNER JOIN and LEFT JOIN? Can someone show me with a small example instead of just explaining it abstractly?", ["SQL", "joins", "INNER JOIN", "LEFT JOIN", "learning style"], "confused", 0.50),
        ("interaction", "Wrote a for-loop to calculate the sum of a list of numbers. Then rewrote it using the built-in sum() function. Both approaches make sense.", ["loops", "for loops", "functions", "built-in functions", "lists"], "confident", 0.12),
        ("struggle", "Tried to create a class with an __init__ method but kept getting 'self' errors. I don't understand why the first parameter has to be self.", ["OOP", "classes", "__init__", "self parameter", "constructors"], "confused", 0.55),
        ("breakthrough", "Conditionals with elif chains are like a decision flowchart. You check each condition in order and take the first path that's true.", ["conditionals", "elif", "control flow", "flowcharts", "mental models"], "confident", 0.08),
        ("question", "How do you sort a list of objects by a specific attribute? Like sorting students by their grade?", ["sorting", "lists", "OOP", "objects", "key functions"], "neutral", 0.30),
        ("interaction", "Completed the debugging exercise by adding print statements to trace the flow of a recursive function. Found the bug was in the base case.", ["debugging", "recursion", "base case", "print statements", "functions"], "neutral", 0.25),
        ("insight", "Realized that SQL tables are like spreadsheets and each row is like one entry. A JOIN combines two spreadsheets side by side based on a matching column.", ["SQL", "joins", "tables", "mental models", "spreadsheet analogy"], "neutral", 0.20),
    ]


def _memories_raj():
    """Low-engagement, no prior experience, slowly progressing."""
    return [
        ("struggle", "I've never programmed before and everyone else seems to already know this stuff. The terminology alone is overwhelming -- variable, function, loop, array.", ["programming basics", "vocabulary", "variables", "functions", "loops", "arrays"], "frustrated", 0.70),
        ("question", "What's the difference between a for loop and a while loop? When do I use which one?", ["for loops", "while loops", "loops", "control flow"], "confused", 0.50),
        ("interaction", "Managed to write my first working loop that prints numbers 1 through 5. It took me an hour but I feel good about it.", ["loops", "for loops", "printing", "first program"], "confident", 0.25),
        ("struggle", "Sorting algorithms are way over my head. The professor showed bubble sort and quicksort in the same lecture and I couldn't follow either one.", ["sorting", "bubble sort", "quicksort", "algorithms"], "frustrated", 0.75),
        ("question", "What does 'return' do in a function? I keep confusing it with 'print'. They both seem to give me output.", ["functions", "return values", "print", "output", "programming basics"], "confused", 0.55),
        ("struggle", "Recursion is impossible. A function that calls itself? My brain goes in circles trying to think about it. I need a completely different explanation.", ["recursion", "functions", "call stack", "conceptual difficulty"], "frustrated", 0.72),
        ("interaction", "Practiced basic conditionals with simple if-else statements. I can handle two branches but adding elif makes it confusing.", ["conditionals", "if-else", "elif", "control flow"], "neutral", 0.38),
    ]


def _memories_suki():
    """High-engagement, strong in data structures and algorithms, mastering OOP."""
    return [
        ("interaction", "Implemented a graph using an adjacency list and wrote BFS and DFS traversals. Compared their use cases: BFS for shortest path, DFS for topological sorting.", ["data structures", "graphs", "BFS", "DFS", "algorithms", "adjacency list"], "confident", 0.05),
        ("breakthrough", "Inheritance creates an 'is-a' relationship (Dog is an Animal) while composition creates a 'has-a' relationship (Car has an Engine). Knowing which to use is key to good design.", ["OOP", "inheritance", "composition", "classes", "design principles"], "confident", 0.04),
        ("interaction", "Wrote SQL queries with multiple JOINs and subqueries to solve complex analytical questions. Used EXPLAIN to understand query execution plans.", ["SQL", "joins", "subqueries", "query optimization", "EXPLAIN"], "confident", 0.06),
        ("insight", "The strategy pattern in OOP is like having interchangeable algorithms. Instead of if-else chains, you encapsulate each strategy in its own class.", ["OOP", "design patterns", "strategy pattern", "classes", "algorithms"], "confident", 0.05),
        ("question", "How do databases handle concurrent writes? What happens if two transactions try to update the same row at the same time?", ["SQL", "transactions", "concurrency", "database internals", "locking"], "neutral", 0.15),
        ("interaction", "Implemented a min-heap from scratch and used it to solve the 'k largest elements' problem. Understood why heap operations are O(log n).", ["data structures", "heaps", "algorithms", "time complexity", "priority queues"], "confident", 0.06),
        ("breakthrough", "Realized that most sorting algorithms are just different strategies for the same problem, optimized for different scenarios. There's no single 'best' sort.", ["sorting", "algorithms", "trade-offs", "time complexity", "space complexity"], "confident", 0.04),
        ("interaction", "Designed a class hierarchy for a library system: Item -> Book, DVD, Magazine. Used abstract methods to enforce that all items implement check_out() and return_item().", ["OOP", "classes", "inheritance", "abstract classes", "abstract methods"], "confident", 0.05),
        ("insight", "SQL indexes are a trade-off: they speed up reads but slow down writes because the index must be updated on every INSERT/UPDATE/DELETE.", ["SQL", "database indexes", "trade-offs", "query optimization", "performance"], "confident", 0.06),
        ("interaction", "Helped a study group understand recursion by walking through merge sort step by step on a whiteboard. Breaking the array in half recursively until single elements.", ["recursion", "sorting", "merge sort", "algorithms", "teaching"], "confident", 0.05),
        ("question", "What's the difference between an interface and an abstract class? Python doesn't have interfaces natively -- how do we handle that?", ["OOP", "interfaces", "abstract classes", "Python", "design patterns"], "neutral", 0.12),
    ]


def _memories_oluwaseun():
    """Medium-engagement, good on loops/conditionals, learning OOP and pointers."""
    return [
        ("interaction", "Completed all the loop exercises including nested loops for printing patterns (triangles, squares). Took time but got them all correct.", ["loops", "nested loops", "patterns", "for loops"], "confident", 0.15),
        ("struggle", "Classes and objects are confusing. I understand that a class is a template but I don't see why I can't just use functions and dictionaries for everything.", ["OOP", "classes", "objects", "functions", "dictionaries"], "confused", 0.45),
        ("question", "What are pointers and why do some languages have them? Python doesn't seem to have pointers, or does it?", ["pointers", "references", "Python", "memory", "programming languages"], "confused", 0.40),
        ("interaction", "Wrote functions to search and sort a list of student records. Used conditional statements to handle edge cases like empty lists.", ["functions", "sorting", "conditionals", "lists", "edge cases"], "confident", 0.18),
        ("breakthrough", "SQL JOINs clicked when I thought of them as matching rows from two tables based on a shared column, like matching students to their enrollments by student_id.", ["SQL", "joins", "foreign keys", "tables", "mental models"], "confident", 0.10),
        ("struggle", "Inheritance is hard to wrap my head around. I created a subclass but couldn't figure out how to call the parent's __init__ using super(). Kept getting errors.", ["inheritance", "OOP", "classes", "super()", "__init__", "constructors"], "frustrated", 0.52),
        ("question", "What's the difference between a list and an array? My textbook uses both terms and I'm not sure if they mean the same thing in Python.", ["arrays", "lists", "data structures", "terminology", "Python"], "neutral", 0.30),
        ("interaction", "Practiced SQL GROUP BY queries on the sample database. Successfully grouped orders by customer and computed total spending per customer.", ["SQL", "GROUP BY", "aggregate functions", "queries"], "confident", 0.15),
        ("insight", "Debugging is like being a detective -- you look at the symptoms (the error), gather clues (print statements, stack trace), and work backwards to find the cause.", ["debugging", "problem solving", "error messages", "stack trace", "mental models"], "confident", 0.10),
    ]


MEMORY_GENERATORS = [
    _memories_fatima,
    _memories_liam,
    _memories_meiling,
    _memories_carlos,
    _memories_anya,
    _memories_kwame,
    _memories_isabella,
    _memories_raj,
    _memories_suki,
    _memories_oluwaseun,
]


async def main():
    conn = await asyncpg.connect(DB_DSN)

    try:
        # ── 1. Create Users ────────────────────────────
        student_ids: list[uuid.UUID] = []
        now = datetime.now(timezone.utc)

        print("Creating 10 new students...")
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
            if s["engagement"] == "low":
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

        print(f"\nTotal NEW memory records created: {total_memories}")

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
        print("INJECTION COMPLETE (10 new students)")
        print("=" * 50)
        print(f"  Total mock students:     {user_count}")
        print(f"  Total enrollments:       {enrollment_count}")
        print(f"  Total student profiles:  {profile_count}")
        print(f"  Total memory records:    {memory_count}")
        print(f"  Course ID:               {COURSE_ID}")

        # Show concept overlap
        concept_rows = await conn.fetch(
            """
            SELECT unnest(concepts) AS concept, count(DISTINCT student_id) AS student_count
            FROM memory_records
            WHERE course_id = $1 AND source = 'mock_injection'
            GROUP BY concept
            HAVING count(DISTINCT student_id) >= 3
            ORDER BY student_count DESC, concept
            LIMIT 25
            """,
            COURSE_ID,
        )
        print(f"\n  Top shared concepts (appearing in 3+ students):")
        for row in concept_rows:
            print(f"    {row['concept']:35s}  ({row['student_count']} students)")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
