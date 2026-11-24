---
title: Do you need to sign a Relay pagination cursor?
description: Here I am talking about relay pagination and whether to sign a cursor or not
published: true
cover_image: "https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/relay-cursor-signing/cover.png"
tags:
  - graphql
  - relay
  - go
  - nestjs
series: Graphql
---

## td;dr

**No**. The [Relay Cursor Connections spec](https://relay.dev/graphql/connections.htm) never asks for it.

AFAIK the spec says:

- Cursor represents the position of an item inside a list of items ([ref](https://www.howtographql.com/react-relay/8-pagination)).
- Every edge has a `cursor`, and the spec calls it an opaque string.

**That is all**. Nothing says the cursor must be signed, encrypted or tied to the query that issued it. "Opaque" is a contract with the client (do not look inside), not a security property.

## NodeJS/NestJS -- Signed Cursor

When I started building GraphQL APIs I was encoding, signing and decoding. A concrete example would be [smart-novel@1.0.0](https://github.com/Ponos-OS/smart-novel/releases/tag/v1.0.0), there a cursor would have looked like this: `eyJhIjoiTVMyWVo3Wkl5WkZSMW1fM1FkaHhubSIsImsiOlsiMWM3NjJlMTgtNzZiMS00YWU4LTg1ZjctZWRmYmUzMjAxODBmIl19.KZX-ximd3leLM_1k0SXAPxZjaysKAvHzEcMrGf3-Tjk`

```bash
$ node -p 'JSON.parse(Buffer.from(process.argv[1].split(".")[0], "base64url"))' 'eyJhIjoiTVMyWVo3Wkl5WkZSMW1fM1FkaHhubSIsImsiOlsiMWM3NjJlMTgtNzZiMS00YWU4LTg1ZjctZWRmYmUzMjAxODBmIl19.KZX-ximd3leLM_1k0SXAPxZjaysKAvHzEcMrGf3-Tjk'

{
  a: 'MS2YZ7ZIyZFR1m_3Qdhxnm',
  k: [ '1c762e18-76b1-4ae8-85f7-edfbe320180f' ]
}
```

The cursor has three parts, and the code is in [apps/backend/src/modules/cursor/cursor-codec.service.ts](https://github.com/Ponos-OS/smart-novel/blob/v1.0.0/apps/backend/src/modules/cursor/cursor-codec.service.ts):

```
<base64url JSON payload>.<base64url HMAC-SHA256 signature>
```

`k`:

- The position of the cursor.
- The id of **the last row** on the cursor I just picked to decode its cursor. The next request starts after that row.
- In this case it is `[novelId]`.
- It's an array, but the type is [string], so it always holds exactly one UUID.
- The array leaves room for a composite key later.

`a`:

- The audience of the cursor.
- Identifies the query the cursor was issued for.
- It's built by [`buildAudience` in shared/utils/cursor-audience.util.ts](https://github.com/Ponos-OS/smart-novel/blob/v1.0.0/apps/backend/src/shared/utils/cursor-audience.util.ts#L27-L45):
  1.  Accepts `connection`, and `query`. `connection` is the connection's name. [query holds the filters](https://github.com/Ponos-OS/smart-novel/blob/v1.0.0/apps/backend/src/modules/novel/services/novel.service.ts#L155), the scope (parent id, viewer) and [any sort the client chose](https://github.com/Ponos-OS/smart-novel/blob/v1.0.0/apps/backend/src/modules/novel/services/novel.service.ts#L145-L152).
  2.  [Canonicalize it](https://github.com/Ponos-OS/smart-novel/blob/v1.0.0/apps/backend/src/shared/utils/cursor-audience.util.ts#L5): sort keys, drop `undefined`, and turn dates into ISO strings. Equal queries then serialize to the same string.
  3.  [Hash it](https://github.com/Ponos-OS/smart-novel/blob/v1.0.0/apps/backend/src/shared/utils/cursor-audience.util.ts#L41-L44) with SHA-256, encode as base64url, and keep the first 22 characters.

So `MS2YZ7ZIyZFR1m_3Qdhxnm` is a hash, not a readable value. We can't reverse it. We can only recompute it from a candidate query and compare. [`decode(cursor, audience)`](https://github.com/Ponos-OS/smart-novel/blob/v1.0.0/apps/backend/src/modules/cursor/cursor-codec.service.ts#L44-L80) throws a `BadRequestException` if the cursor's a doesn't match the current query's audience. This stops a cursor from one list, filter, or viewer being replayed on another.

The signature after the `.`

This is an HMAC-SHA256 of the base64url payload, keyed with [`CURSOR_SIGNING_SECRET`](https://github.com/Ponos-OS/smart-novel/blob/v1.0.0/.env.example#L100). It stops clients from forging or editing cursors. decode checks it with [`timingSafeEqual`](https://github.com/Ponos-OS/smart-novel/blob/v1.0.0/apps/backend/src/modules/cursor/cursor-codec.service.ts#L60) before it parses the payload.

Essentially the payload is encoded, not encrypted. Anyone can read `a` and `k`, as we just did, but nobody can change them without the `CURSOR_SIGNING_SECRET`.

## Golang/Ent -- Unsigned Cursor

But later when I tried to use [Ent](https://github.com/ent/ent) framework in Golang I realized I could have dropped the signing cursor part.

The cursor in Golang would look like this: `gqFpxBD9fOCeg+NNroyEqHImBq4uoXajWlpa`:

It's [`MessagePack`](https://msgpack.org/), base64-encoded. Ent's pagination cursor holds the row's ID and the sort value and as you can see here we used Python and bash to decode it (you can see how to do it [here in Golang](#how-you-can-decode-the-ent-cursor)):

```bash
$ echo 'gqFpxBD9fOCeg+NNroyEqHImBq4uoXajWlpa' | base64 -d | xxd; python3 -c "import base64;print(base64.b64decode('gqFpxBD9fOCeg+NNroyEqHImBq4uoXajWlpa'+'=='*0).hex())"
00000000: 82a1 69c4 10fd 7ce0 9e83 e34d ae8c 84a8  ..i...|....M....
00000010: 7226 06ae 2ea1 76a3 5a5a 5a              r&....v.ZZZ
82a169c410fd7ce09e83e34dae8c84a8722606ae2ea176a35a5a5a
```

The raw bytes are:

```
82 a1 69 c4 10 fd7ce09e83e34dae8c84a8722606ae2e a1 76 a3 5a5a5a
```

MessagePack uses the first byte of each item to say what it is:

| Byte          | Meaning                                                                        |
| ------------- | ------------------------------------------------------------------------------ |
| 82            | A map with 2 entries (`i`, and `v`)                                            |
| a1            | A string of 1 byte                                                             |
| 69            | The `i` key (identifier for cursor-based pagination)                           |
| c4            |                                                                                |
| 10            | the blob is 16 bytes                                                           |
| next 16 bytes | The blob itself, a UUID                                                        |
| a1 76         | The `v` key (sort criteria)                                                    |
| a3            |                                                                                |
| 5a 5a 5a      | "ZZZ" (the novel name, I was just testing, so that's why the name is so weird) |

- `i` is "fd7ce09e-83e3-4dae-8c84-a8722606ae2e", a novel ID.
- `v` is "ZZZ". It is **the value of the field** the list is ordered by, here the novel name.

  The cursor stores it so the database can resume after that row/cursor. Ent orders by (value, id), and the **ID is our tie breaker**.

In Golang I am generating the cursor [`apps/backend/internal/graph/scalar/cursor.go`](https://github.com/Ponos-OS/smart-novel/blob/v2.0.0/apps/backend/internal/graph/scalar/cursor.go).

## How You can Decode the Ent Cursor

```go
package main

import (
	"fmt"

	"github.com/google/uuid"

	"entgo.io/contrib/entgql"
)

func main() {
	var decodedCursor entgql.Cursor[uuid.UUID]
	if err := decodedCursor.UnmarshalGQL("gqFpxBD9fOCeg+NNroyEqHImBq4uoXajWlpa"); err != nil {
		panic(err)
	}
	fmt.Printf("%+v\n", decodedCursor)
	// {ID:fd7ce09e-83e3-4dae-8c84-a8722606ae2e Value:ZZZ}
}
```
