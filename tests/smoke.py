# Copyright 2018 John Reese
# Licensed under the MIT license

import aiosqlite
import aiounittest
import asyncio
import sys

from pathlib import Path
from .helpers import setup_logger

TEST_DB = Path("test.db")


class SmokeTest(aiounittest.AsyncTestCase):
    @classmethod
    def setUpClass(cls):
        setup_logger()

    def setUp(self):
        if TEST_DB.exists():
            TEST_DB.unlink()

    def tearDown(self):
        if TEST_DB.exists():
            TEST_DB.unlink()

    async def test_connection(self):
        async with aiosqlite.connect(TEST_DB) as db:
            assert isinstance(db, aiosqlite.Connection)

    async def test_multiple_connections(self):
        async with aiosqlite.connect(TEST_DB) as db:
            await db.execute(
                "create table multiple_connections "
                "(i integer primary key asc, k integer)"
            )

        async def do_one_conn(i):
            async with aiosqlite.connect(TEST_DB) as db:
                await db.execute("insert into multiple_connections (k) values (?)", [i])
                await db.commit()

        await asyncio.gather(*[do_one_conn(i) for i in range(10)])

        async with aiosqlite.connect(TEST_DB) as db:
            cursor = await db.execute("select * from multiple_connections")
            rows = await cursor.fetchall()

        assert len(rows) == 10

    async def test_multiple_queries(self):
        async with aiosqlite.connect(TEST_DB) as db:
            await db.execute(
                "create table multiple_queries "
                "(i integer primary key asc, k integer)"
            )

            await asyncio.gather(
                *[
                    db.execute("insert into multiple_queries (k) values (?)", [i])
                    for i in range(10)
                ]
            )

            await db.commit()

        async with aiosqlite.connect(TEST_DB) as db:
            cursor = await db.execute("select * from multiple_queries")
            rows = await cursor.fetchall()

        assert len(rows) == 10

    async def test_iterable_cursor(self):
        async with aiosqlite.connect(TEST_DB) as db:
            cursor = await db.cursor()
            await cursor.execute(
                "create table iterable_cursor " "(i integer primary key asc, k integer)"
            )
            await cursor.executemany(
                "insert into iterable_cursor (k) values (?)", [[i] for i in range(10)]
            )
            await db.commit()

        async with aiosqlite.connect(TEST_DB) as db:
            cursor = await db.execute("select * from iterable_cursor")
            rows = []
            async for row in cursor:
                rows.append(row)

        assert len(rows) == 10

    async def test_context_cursor(self):
        async with aiosqlite.connect(TEST_DB) as db:
            async with db.cursor() as cursor:
                await cursor.execute(
                    "create table context_cursor "
                    "(i integer primary key asc, k integer)"
                )
                await cursor.executemany(
                    "insert into context_cursor (k) values (?)",
                    [[i] for i in range(10)],
                )
                await db.commit()

        async with aiosqlite.connect(TEST_DB) as db:
            async with db.execute("select * from context_cursor") as cursor:
                rows = []
                async for row in cursor:
                    rows.append(row)

        assert len(rows) == 10

    async def test_connection_properties(self):
        async with aiosqlite.connect(TEST_DB) as db:
            assert db.total_changes == 0

            async with db.cursor() as cursor:
                assert db.in_transaction == False
                await cursor.execute(
                    "create table test_properties "
                    "(i integer primary key asc, k integer, d text)"
                )
                await cursor.execute(
                    "insert into test_properties (k, d) values (1, 'hi')"
                )
                assert db.in_transaction == True
                await db.commit()
                assert db.in_transaction == False

            assert db.total_changes == 1

            assert db.row_factory == None
            assert db.text_factory == str

            async with db.cursor() as cursor:
                await cursor.execute("select * from test_properties")
                row = await cursor.fetchone()
                assert type(row) == tuple
                assert row == (1, 1, "hi")
                try:
                    row["k"]
                    assert False, "tuple row should only be indexable by integers"
                except TypeError:
                    pass

            db.row_factory = aiosqlite.Row
            db.text_factory = bytes
            assert db.row_factory == aiosqlite.Row
            assert db.text_factory == bytes

            async with db.cursor() as cursor:
                await cursor.execute("select * from test_properties")
                row = await cursor.fetchone()
                assert type(row) == aiosqlite.Row
                assert row[1] == 1
                assert row[2] == b"hi"
                assert row["k"] == 1
                assert row["d"] == b"hi"
