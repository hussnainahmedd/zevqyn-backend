-- Migration: Add junction tables for portfolio skills, education, and certificates

-- 1. Portfolio Skills
CREATE TABLE IF NOT EXISTS portfolio_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT portfolio_skills_unique UNIQUE (portfolio_id, skill_id)
);
CREATE INDEX IF NOT EXISTS idx_portfolio_skills_portfolio_id ON portfolio_skills(portfolio_id);

-- 2. Portfolio Education
CREATE TABLE IF NOT EXISTS portfolio_education (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    education_id UUID NOT NULL REFERENCES education(id) ON DELETE CASCADE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT portfolio_education_unique UNIQUE (portfolio_id, education_id)
);
CREATE INDEX IF NOT EXISTS idx_portfolio_education_portfolio_id ON portfolio_education(portfolio_id);

-- 3. Portfolio Certificates
CREATE TABLE IF NOT EXISTS portfolio_certificates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    certificate_id UUID NOT NULL REFERENCES certificates(id) ON DELETE CASCADE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT portfolio_certificates_unique UNIQUE (portfolio_id, certificate_id)
);
CREATE INDEX IF NOT EXISTS idx_portfolio_certificates_portfolio_id ON portfolio_certificates(portfolio_id);
