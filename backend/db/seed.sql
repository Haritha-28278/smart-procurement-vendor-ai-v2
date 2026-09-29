-- Seed Data for Smart Procurement Vendor AI
-- Passwords: All accounts use password: password123
-- Hash generated using bcrypt for 'password123': $2b$12$r4Y9t2NU4XcZaOwN8RUTOuiB17wjQTdpVpwYO6oTyNk.aFfXBaLrq

INSERT INTO users (email, password_hash, full_name, role)
VALUES
    ('admin@smartprocure.ai', '$2b$12$r4Y9t2NU4XcZaOwN8RUTOuiB17wjQTdpVpwYO6oTyNk.aFfXBaLrq', 'Sarah Chen (Admin)', 'Admin'),
    ('manager@smartprocure.ai', '$2b$12$r4Y9t2NU4XcZaOwN8RUTOuiB17wjQTdpVpwYO6oTyNk.aFfXBaLrq', 'Michael Torres (Procurement Lead)', 'Procurement Manager'),
    ('vendor@apexlogistics.com', '$2b$12$r4Y9t2NU4XcZaOwN8RUTOuiB17wjQTdpVpwYO6oTyNk.aFfXBaLrq', 'David Ross (Apex Logistics)', 'Vendor')
ON CONFLICT (email) DO NOTHING;

-- 5 Sample Vendors
INSERT INTO vendors (name, category, pricing, certifications, past_performance, performance_rating, location, contact_email, contact_phone, website)
VALUES
    (
        'Apex Global Logistics & Freight',
        'Logistics & Supply Chain',
        'Moderate',
        'ISO 9001:2015, C-TPAT Certified, IATA Authorized, Green Freight Partner',
        'Maintained a 98.4% on-time delivery rate across 1,200 international shipments in 2024. SLA claims under 0.2%. Strong cold-chain capabilities.',
        4.85,
        'Chicago, IL, USA',
        'sales@apexlogistics.com',
        '+1 (312) 555-0144',
        'https://apexlogistics.example.com'
    ),
    (
        'Vanguard CyberShield Technologies',
        'IT & Cybersecurity',
        'Premium',
        'SOC 2 Type II, ISO 27001, FedRAMP High Ready, PCI-DSS Level 1',
        'Deployed enterprise zero-trust security infrastructure for 4 Fortune 500 financial institutions. Zero security breaches during 5-year tenure.',
        4.92,
        'Austin, TX, USA',
        'enterprise@vanguardcyber.io',
        '+1 (512) 555-0199',
        'https://vanguardcyber.example.com'
    ),
    (
        'EcoPack Sustainable Materials Ltd',
        'Packaging & Raw Materials',
        'Budget',
        'FSC Certified, Cradle to Cradle Gold, ISO 14001, Biodegradable Standard EN 13432',
        'Supplied compostable corrugated and molded fiber packaging to 40+ consumer brands. Average lead time 14 days, unit defect rate < 0.05%.',
        4.45,
        'Portland, OR, USA',
        'b2b@ecopackmfg.com',
        '+1 (503) 555-0182',
        'https://ecopackmfg.example.com'
    ),
    (
        'Precision Dynamics Industrial Robotics',
        'Industrial Machinery',
        'Premium',
        'ISO 9001, CE Mark, OSHA Compliant Robotics, UL Certified',
        'Engineered automated sorting and assembly arms for high-throughput manufacturing plants. Mean Time Between Failures (MTBF) exceeding 18,000 hours.',
        4.70,
        'Detroit, MI, USA',
        'solutions@precisiondyn.com',
        '+1 (313) 555-0128',
        'https://precisiondyn.example.com'
    ),
    (
        'Nexus Cloud Infrastructure Solutions',
        'IT & Cybersecurity',
        'Moderate',
        'AWS Premier Tier Services Partner, Microsoft Solutions Partner, ISO 27001',
        'Migrated 12 enterprise ERP stacks to multi-cloud Kubernetes architectures. Saved clients an average of 28% in annual cloud spend.',
        4.60,
        'Seattle, WA, USA',
        'consulting@nexuscloud.tech',
        '+1 (206) 555-0177',
        'https://nexuscloud.example.com'
    )
ON CONFLICT (contact_email) DO NOTHING;

-- 2 Sample RFQs
INSERT INTO rfqs (title, category, requirements, budget, deadline, status, created_by)
VALUES
    (
        'Enterprise Multi-Region Cloud Migration & Zero-Trust Defense',
        'IT & Cybersecurity',
        'Requires architecting and executing migration of legacy on-premises ERP systems to a resilient cloud cluster. Must implement Zero-Trust access control, automated threat detection, 99.99% uptime SLA, and SOC 2 Type II compliance.',
        150000.00,
        CURRENT_DATE + INTERVAL '30 days',
        'Open',
        2
    ),
    (
        'Eco-Friendly B2B Packaging & Global Cold Chain Distribution',
        'Logistics & Supply Chain',
        'Procurement of 100% biodegradable corrugated shipping containers (50,000 units/quarter) with temperature-monitored refrigerated freight transport for pharmaceutical products across North America and EU.',
        85000.00,
        CURRENT_DATE + INTERVAL '45 days',
        'Open',
        2
    )
ON CONFLICT (title) DO NOTHING;

-- Quotes for RFQ #1 (IT & Cybersecurity)
INSERT INTO quotes (rfq_id, vendor_id, quote_amount, delivery_timeline_days, proposal_details, status)
VALUES
    (
        1,
        2, -- Vanguard CyberShield
        142000.00,
        45,
        'Complete end-to-end zero-trust implementation with 24/7 SOC integration, FedRAMP-aligned encryption, and seamless ERP containerization.',
        'Shortlisted'
    ),
    (
        1,
        5, -- Nexus Cloud Infrastructure
        128000.00,
        60,
        'Multi-cloud Kubernetes migration plan with automated Terraform deployment pipelines, cost optimization governance, and AWS/Azure dual-redundancy.',
        'Submitted'
    );

-- Quotes for RFQ #2 (Logistics & Supply Chain)
INSERT INTO quotes (rfq_id, vendor_id, quote_amount, delivery_timeline_days, proposal_details, status)
VALUES
    (
        2,
        1, -- Apex Global Logistics
        79500.00,
        20,
        'Full temperature-controlled cold chain distribution with real-time IoT temperature sensors and bonded customs clearance in US/EU hubs.',
        'Shortlisted'
    ),
    (
        2,
        3, -- EcoPack Sustainable Materials
        45000.00,
        15,
        'FSC-certified biodegradable corrugated packaging production (50,000 units) with custom thermal insulation inserts.',
        'Submitted'
    );

-- Initial AI Analysis cache for top matching quotes
INSERT INTO ai_analysis (rfq_id, vendor_id, match_score, reasoning, risk_flags)
VALUES
    (
        1,
        2,
        94,
        'Vanguard CyberShield demonstrates near-perfect alignment with zero-trust defense and SOC 2 requirements. Their Fortune 500 track record and high SLA compliance justify the premium quote, which falls safely within the $150,000 budget.',
        '["Premium pricing near budget ceiling ($142,000 vs $150,000 budget)", "Requires dedicated internal stakeholder for weekly zero-trust audits"]'
    ),
    (
        1,
        5,
        86,
        'Nexus Cloud provides strong cloud migration capabilities and offers a 15% cost savings compared to Vanguard. However, their primary expertise is DevOps architecture rather than specialized zero-trust cyber defense.',
        '["Timeline is 15 days longer than alternative bidder (60 days vs 45 days)", "Secondary cyber-defense partner may be needed for FedRAMP adherence"]'
    ),
    (
        2,
        1,
        91,
        'Apex Global Logistics possesses verified cold-chain infrastructure, C-TPAT certification, and an exceptional 98.4% on-time record for pharmaceutical transit. The quoted $79,500 is comfortably within the $85,000 threshold.',
        '["Fluctuations in international jet fuel surcharges could impact final billing", "Requires clear protocol for border customs inspection delays"]'
    )
ON CONFLICT (rfq_id, vendor_id) DO NOTHING;
