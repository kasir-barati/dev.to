---
title: "JSONB Fields in PostgreSQL & Prisma"
published: true
description: "A practical guide to using JSONB fields in PostgreSQL with Prisma, covering validation with check constraints and custom functions, plus when to reach for pg_jsonschema."
tags:
  - postgres
  - prisma
  - databasedesign
cover_image: "https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/jsonb-fields-in-postgres-and-prisma/cover.png"
series: Databas Design
---

Usually when you know about your data structure before hand, and it is well structured with relations you just use the typical fields types. But when it is an unstructured field where we do not know the structure I do not like to start guessing, and defining them using typical scalar types which also mean separate migration SQL queries.

But then I feel like eating my food form the back of my head since it is kinda janky and hard to maintain if you ask me when using SQL database engine instead of modern database engines such as MongoDB which has builtin support for JSON. Though I know it is not always possible to utilize MongoDB. That is why I decided to talk about `JSONB` fields in PostgreSQL.

---

The `JSONB` data type is used to store JSON data in a decomposed binary format. Unlike [the standard JSON type](https://www.postgresql.org/docs/current/datatype-json.html) that stores raw text and requires reparsing on every query, JSONB **strips whitespace**, **sorts keys**, and **removes duplicate keys**, allowing for significantly **faster processing and data retrieval**.

> [!NOTE]
>
> **Decomposed binary** means the **JSON text is parsed and converted** into an **optimized binary tree structure** upon storage, rather than kept as a raw string.

Though using the field as it is might not be the best idea since client can literally stores an array of strings, numbers, or other values instead of a JSON value. This is about general data validation inside your database engine.

```sql
CREATE TABLE users (
    id       SERIAL PRIMARY KEY,
    metadata JSONB NOT NULL CHECK (jsonb_typeof(metadata) = 'object')
);
-- Succeeds
INSERT INTO users (metadata) VALUES ('{"type": "foo"}'::jsonb);
-- Fails
INSERT INTO users (metadata) VALUES ('["a","b"]'::jsonb);
INSERT INTO users (metadata)
       VALUES
       (\(\)[ "a", "b", "c" ]\)$::JSONB),
       (\(\)0.2523562\)::JSONB),
       (\(\)null\)::JSONB);
```

So this is the simplest check you might wanna do. But when I watched this YouTube Video titled ["Even JSONB In Postgres Needs Schemas | POSETTE 2024"](https://youtu.be/F6X60ln2VNc), so this way at least you are not completely blind to what goes inside the JSONB field, but this does not mean I would do it for all fields, if the field is a readonly field used for reporting, analytics, or sending to another external service which does not care about the structure or has its own validation logic.

BTW I wanted to also show you how you might wanna do it in [Prisma](https://www.prisma.io) since I like the ORM. Though in Prisma you cannot create functions using their schema language. So we have to create an empty migration file and then create the function manually (this is an example I saw in the aforementioned YouTube video):

```sql
CREATE OR REPLACE FUNCTION check_ruleset_valid(ruleset JSONB)
RETURNS BOOLEAN LANGUAGE SQL
IMMUTABLE AS $$
    SELECT jsonb_typeof(ruleset) = 'object' AND
           ruleset -> 'tbl' IS NOT NULL AND
           jsonb_typeof(ruleset -> 'type') = 'string';
$$;
```

In this example, we are assuming we have a field in a table called `ruleset` that stores JSONB data. This function is checking the key-value structure of the JSON data to ensure it conforms to the expected schema.

> [!TIP]
>
> Use <https://nexteam.co.uk/pg-jsonschema-gen/v1/index.html> to generate a JSON the function you will be needing.

Then in your prisma schema file you can simply say:

```prisma
model users {
  id        Int    @id @default(autoincrement())
  ruleset   Json?  // specialised JSONB for rule systems
  metadata  Json?  // maps to JSONB in PostgreSQL

  @@check("metadata_chk", "jsonb_typeof(metadata) = 'object'")
  @@check("ruleset_structure_chk", "check_ruleset_valid(ruleset)")
}
```

That Prisma schema will generate the following SQL or something like it:

```sql
CREATE TABLE "users" (
  id INTEGER PRIMARY KEY,
  metadata JSONB,
  ruleset JSONB,

  CONSTRAINT "metadata_chk" CHECK (jsonb_typeof(metadata) = 'object')
  CONSTRAINT "ruleset_structure_chk" CHECK (check_ruleset_valid(ruleset))
);
```

So here I am imagining you have dynamic rule system:

```json
{
  "type": "rules",
  "decisions": [{ "fact": "country", "op": "eq", "value": "GB" }]
}
```

> [!TIP]
>
> - You can use the same function in multiple tables and you are not limited to using it only in a single table.
> - From checking for a pulse to doing a full medical scan: If your `ruleset` JSON has nested arrays, specific value enums, or absolutely must **not** have extra random fields, manual `jsonb_typeof` checks become a nightmare of deeply nested SQL operators. In such cases you can use [`pg_jsonschema`](https://github.com/supabase/pg_jsonschema).
