-- Atlas — Postgres schema for the deductive knowledge architecture (v1).
-- Mirrors engine/atlas_engine/schemas.py and ARCHITECTURE.md §5.3.
-- The engine is the source of truth for node/edge types; keep this in sync.

CREATE EXTENSION IF NOT EXISTS vector;

-- Source + provenance base ---------------------------------------------------
CREATE TABLE documents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title         text NOT NULL,
  source_path   text NOT NULL,
  architecture  text NOT NULL DEFAULT 'deductive',
  content_hash  text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE pages (
  document_id   uuid REFERENCES documents(id),
  page_no       int NOT NULL,
  text          text NOT NULL,
  blocks        jsonb NOT NULL,   -- [{bbox, char_start, char_end, latex?}]
  PRIMARY KEY (document_id, page_no)
);

-- Knowledge graph ------------------------------------------------------------
CREATE TYPE node_type AS ENUM (
  'definition','axiom','notation','lemma','theorem',
  'proposition','corollary','proof','example','counterexample','remark');

CREATE TABLE nodes (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id   uuid REFERENCES documents(id),
  type          node_type NOT NULL,
  label         text NOT NULL,
  statement     text NOT NULL,
  embedding     vector(1024),
  verified      boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX nodes_embedding_idx ON nodes USING hnsw (embedding vector_cosine_ops);

CREATE TYPE edge_type AS ENUM (
  'depends_on','uses','corollary_of','special_case_of','proves',
  'example_of','counterexample_to','generalizes','equivalent_to','intuition_for');

CREATE TABLE edges (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  src           uuid REFERENCES nodes(id),
  dst           uuid REFERENCES nodes(id),
  type          edge_type NOT NULL,
  in_dag        boolean NOT NULL,   -- whether this edge constrains learning order
  confidence    real,
  verified      boolean NOT NULL DEFAULT false,
  UNIQUE (src, dst, type),
  CHECK (src <> dst)
);

-- Anti-hallucination: every node/edge traceable to a source span ------------
CREATE TABLE citations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  node_id       uuid REFERENCES nodes(id),
  edge_id       uuid REFERENCES edges(id),
  document_id   uuid REFERENCES documents(id),
  page_no       int NOT NULL,
  char_start    int NOT NULL,
  char_end      int NOT NULL,
  quote         text NOT NULL,        -- must equal source substring at the span
  entailment    text NOT NULL,        -- 'yes' | 'partial' | 'no'
  confidence    real NOT NULL,
  CHECK (num_nonnulls(node_id, edge_id) = 1),
  CHECK (char_end >= char_start)
);

-- Modality decision (rules-as-code output) ----------------------------------
CREATE TABLE node_modality (
  node_id       uuid PRIMARY KEY REFERENCES nodes(id),
  modality      text NOT NULL,   -- self_paced_text|static_diagram|stepwise_reveal|animation
  features      jsonb NOT NULL,
  rationale     text
);

-- Active processing ----------------------------------------------------------
CREATE TABLE recall_items (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  node_id       uuid REFERENCES nodes(id),
  kind          text NOT NULL,   -- cloze|recall|apply|prove_step
  prompt        text NOT NULL,
  answer        text NOT NULL,
  distractors   jsonb,
  grounded      boolean NOT NULL DEFAULT false,
  citation_id   uuid REFERENCES citations(id)
);

-- Learner model: per user x per node ----------------------------------------
CREATE TABLE learner_node_state (
  user_id        uuid NOT NULL,
  node_id        uuid REFERENCES nodes(id),
  p_known        real NOT NULL DEFAULT 0.1,   -- BKT mastery probability
  stability      real,                         -- FSRS
  difficulty     real,                         -- FSRS
  due_at         timestamptz,
  last_review_at timestamptz,
  reps           int NOT NULL DEFAULT 0,
  lapses         int NOT NULL DEFAULT 0,
  state          text NOT NULL DEFAULT 'new',  -- new|learning|review|relearning
  PRIMARY KEY (user_id, node_id)
);

-- Pipeline cache / observability --------------------------------------------
CREATE TABLE extraction_runs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id   uuid REFERENCES documents(id),
  stage         text NOT NULL,        -- ingest|segment|extract|edges|verify|assemble
  input_hash    text NOT NULL,
  status        text NOT NULL,
  metrics       jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, stage, input_hash)
);
