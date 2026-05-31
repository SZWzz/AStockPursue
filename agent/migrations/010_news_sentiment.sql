-- ============================================================================
-- News Sentiment — aggregated news items and stock sentiment
-- ============================================================================

CREATE TABLE IF NOT EXISTS vt_news_items (
    id              SERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    url             TEXT,
    source          VARCHAR(32),
    content         TEXT,
    summary         TEXT,
    published_at    TIMESTAMPTZ,
    sentiment_score DOUBLE PRECISION,
    sentiment_label VARCHAR(16) CHECK (sentiment_label IN ('positive', 'neutral', 'negative')),
    matched_symbols TEXT[] DEFAULT '{}',
    topics          TEXT[] DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(title, source)
);
CREATE INDEX IF NOT EXISTS idx_news_published ON vt_news_items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_symbols ON vt_news_items USING gin(matched_symbols);

CREATE TABLE IF NOT EXISTS vt_stock_sentiment (
    id              SERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    date            DATE NOT NULL,
    sentiment_mean  DOUBLE PRECISION,
    sentiment_std   DOUBLE PRECISION,
    news_count      INTEGER,
    trending_score  DOUBLE PRECISION,
    UNIQUE(symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_stock_sent ON vt_stock_sentiment(symbol, date DESC);
