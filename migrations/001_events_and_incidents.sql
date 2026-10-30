CREATE TABLE events (
    id uuid PRIMARY KEY,
    idempotency_key varchar(128) NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE incidents (
    id uuid PRIMARY KEY,
    event_id uuid NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    system varchar(32) NOT NULL CHECK (system = 'synthetic-finance'),
    component varchar(32) NOT NULL CHECK (component IN ('payments', 'ledger', 'settlement')),
    status varchar(16) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    opened_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at timestamptz,
    CHECK ((status = 'open' AND resolved_at IS NULL)
        OR (status = 'resolved' AND resolved_at IS NOT NULL))
);

CREATE INDEX incidents_opened_idx ON incidents(opened_at DESC, id DESC);
