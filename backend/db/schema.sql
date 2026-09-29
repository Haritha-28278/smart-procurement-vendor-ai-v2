-- Schema for Smart Procurement Vendor AI
-- Tech stack: PostgreSQL (Direct SQL via psycopg2)

DROP TABLE IF EXISTS ai_analysis CASCADE;
DROP TABLE IF EXISTS quotes CASCADE;
DROP TABLE IF EXISTS rfqs CASCADE;
DROP TABLE IF EXISTS vendors CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Users table with Role-Based Access Control (Admin, Procurement Manager, Vendor)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('Admin', 'Procurement Manager', 'Vendor')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Vendors registry
CREATE TABLE IF NOT EXISTS vendors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    pricing VARCHAR(50) NOT NULL, -- e.g. Budget, Moderate, Premium, Enterprise
    certifications TEXT,          -- e.g. ISO 9001, SOC 2 Type II, HIPAA, CE, LEED
    past_performance TEXT,       -- Narrative on reliability, fulfillment, SLA
    performance_rating NUMERIC(3,2) DEFAULT 4.00 CHECK (performance_rating >= 0 AND performance_rating <= 5.0),
    location VARCHAR(150) NOT NULL,
    contact_email VARCHAR(255) UNIQUE,
    contact_phone VARCHAR(50),
    website VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- RFQ (Request for Quotation)
CREATE TABLE IF NOT EXISTS rfqs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) UNIQUE NOT NULL,
    category VARCHAR(100) NOT NULL,
    requirements TEXT NOT NULL,
    budget NUMERIC(12,2) NOT NULL,
    deadline DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'Open' CHECK (status IN ('Open', 'In Review', 'Awarded', 'Closed')),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Quotes submitted by vendors for RFQs
CREATE TABLE IF NOT EXISTS quotes (
    id SERIAL PRIMARY KEY,
    rfq_id INTEGER NOT NULL REFERENCES rfqs(id) ON DELETE CASCADE,
    vendor_id INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    quote_amount NUMERIC(12,2) NOT NULL,
    delivery_timeline_days INTEGER NOT NULL,
    proposal_details TEXT,
    status VARCHAR(50) DEFAULT 'Submitted' CHECK (status IN ('Submitted', 'Shortlisted', 'Accepted', 'Rejected')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_rfq_vendor_quote UNIQUE (rfq_id, vendor_id)
);

-- AI Analysis cache per RFQ + Vendor pair
CREATE TABLE IF NOT EXISTS ai_analysis (
    id SERIAL PRIMARY KEY,
    rfq_id INTEGER NOT NULL REFERENCES rfqs(id) ON DELETE CASCADE,
    vendor_id INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    match_score INTEGER NOT NULL CHECK (match_score >= 0 AND match_score <= 100),
    reasoning TEXT NOT NULL,
    risk_flags TEXT, -- JSON array string or comma separated
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_rfq_vendor_analysis UNIQUE (rfq_id, vendor_id)
);

-- Helpful indexes for query performance
CREATE INDEX IF NOT EXISTS idx_rfqs_status ON rfqs(status);
CREATE INDEX IF NOT EXISTS idx_quotes_rfq ON quotes(rfq_id);
CREATE INDEX IF NOT EXISTS idx_quotes_vendor ON quotes(vendor_id);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_lookup ON ai_analysis(rfq_id, vendor_id);
