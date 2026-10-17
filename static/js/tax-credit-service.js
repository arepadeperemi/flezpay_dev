/**
 * tax-credit-service.js
 * FlezPay Financial Compliance & Credit Health Service Layer
 * 
 * Abstraction layer decoupling the UI from data providers.
 * Currently backed by realistic mock data, asynchronous simulation, and localStorage persistence.
 * When real APIs (Tax Authorities, Credit Bureaus, Open Banking) are connected,
 * replace the simulated implementations below without modifying the UI layer.
 */

(function(window) {
  'use strict';

  // Helper for simulated network latency
  const delay = (ms = 220) => new Promise(resolve => setTimeout(resolve, ms));

  // Storage keys (prefixed to avoid collisions; bumped to v2 for clean currency reset)
  const STORAGE_KEYS = {
    TAX_PROFILE: 'flezpay_tax_profile_v2',
    TAX_SETTINGS: 'flezpay_tax_settings_v2',
    TAX_DOCUMENTS: 'flezpay_tax_docs_v2',
    TAX_INSIGHTS: 'flezpay_tax_insights_v2',
    CREDIT_PLAN: 'flezpay_credit_plan_v2',
    CREDIT_ISSUES: 'flezpay_credit_issues_v2',
    AGENT_SETTINGS: 'flezpay_financial_agent_v2',
  };

  // Helper to obtain logged-in user currency symbol
  const getUserCurrency = () => {
    if (typeof window !== 'undefined') {
      if (typeof window.getUserCurrencySymbol === 'function') return window.getUserCurrencySymbol();
      if (window.STORE_CURRENCY_SYMBOL) return window.STORE_CURRENCY_SYMBOL;
    }
    return '₦';
  };

  // -------------------------------------------------------------------------
  // 1. COUNTRY CONFIGURATIONS
  // -------------------------------------------------------------------------
  const COUNTRY_CONFIGS = {
    NG: {
      code: 'NG',
      name: 'Nigeria',
      currency: '₦',
      currencyCode: 'NGN',
      taxAuthority: 'Federal Inland Revenue Service (FIRS)',
      taxIdLabel: 'Tax Identification Number (TIN)',
      taxIdPlaceholder: 'e.g. 23819284-0001',
      taxIdMask: '•••-•••-0001',
      vatLabel: 'VAT Registration Number',
      vatPlaceholder: 'e.g. 10023485-0001',
      businessRegistrationLabel: 'CAC Registration / RC Number',
      businessRegistrationPlaceholder: 'e.g. RC 1849201',
      supportedTaxTypes: [
        'Private Limited Company (Ltd)',
        'Public Limited Company (Plc)',
        'Business Name / Sole Proprietorship',
        'Incorporated Trustee / NGO'
      ],
      jurisdictions: [
        'Lagos State Internal Revenue Service (LIRS)',
        'Federal Capital Territory IRS (FCT-IRS)',
        'Rivers State Internal Revenue Service (RIRS)',
        'Ogun State Internal Revenue Service (OGIRS)',
        'Kano State Internal Revenue Service (KIRS)',
        'Oyo State Internal Revenue Service (OYIRS)',
        'Other State Revenue Service'
      ],
      filingPeriods: [
        'Monthly (VAT & PAYE Withholding)',
        'Annual Company Income Tax (CIT)',
        'Bi-Annual Interim Assessment'
      ],
      taxRegimes: [
        'Standard CIT (30% on Taxable Profits)',
        'Medium Company Rate (20% for ₦25M - ₦100M)',
        'Small Business Exemption (0% for < ₦25M Turnover)',
        'Pioneer Status Incentive (Tax Holiday)'
      ],
      defaultProfile: {
        legalName: 'FlezPay Technologies Nigeria Ltd',
        tradingName: 'FlezPay Enterprise',
        regNumber: 'RC 1849201',
        tin: '23819284-0001',
        businessType: 'Private Limited Company (Ltd)',
        industry: 'Financial Technology / Digital Commerce',
        country: 'NG',
        state: 'Lagos State Internal Revenue Service (LIRS)',
        city: 'Victoria Island, Lagos',
        address: 'Plot 14 Admiralty Way, Lekki Phase 1',
        postalCode: '101241',
        email: 'compliance@flezpay.com',
        phone: '+234 812 345 6789',
        jurisdiction: 'Lagos State Internal Revenue Service (LIRS)',
        taxRegNumber: '23819284-0001',
        vatNumber: '10023485-0001',
        filingFrequency: 'Monthly (VAT & PAYE Withholding)',
        fiscalYearStart: '01-01',
        fiscalYearEnd: '12-31',
        taxEntityType: 'Private Limited Company (Ltd)',
        taxResidency: 'Nigeria Resident Entity',
        taxRegime: 'Medium Company Rate (20% for ₦25M - ₦100M)'
      }
    },
    US: {
      code: 'US',
      name: 'United States',
      currency: '$',
      currencyCode: 'USD',
      taxAuthority: 'Internal Revenue Service (IRS)',
      taxIdLabel: 'Employer Identification Number (EIN / TIN)',
      taxIdPlaceholder: 'e.g. 12-3456789',
      taxIdMask: '••-•••6789',
      vatLabel: 'State Sales Tax Identification Number',
      vatPlaceholder: 'e.g. ST-9876543-US',
      businessRegistrationLabel: 'State Entity / File Number',
      businessRegistrationPlaceholder: 'e.g. DE-7291048',
      supportedTaxTypes: [
        'Limited Liability Company (LLC)',
        'C-Corporation',
        'S-Corporation',
        'Sole Proprietorship',
        'General Partnership'
      ],
      jurisdictions: [
        'Delaware (Division of Corporations)',
        'California (Franchise Tax Board)',
        'New York (Dept of Taxation & Finance)',
        'Texas (Comptroller of Public Accounts)',
        'Florida (Department of Revenue)',
        'Wyoming (Secretary of State)'
      ],
      filingPeriods: [
        'Quarterly Estimated (Form 1120-W / 1040-ES)',
        'Annual Corporate Return (Form 1120 / 1120-S)',
        'Monthly State Sales Tax'
      ],
      taxRegimes: [
        'Federal Corporate Income Tax (21%)',
        'Pass-Through Entity Election (PTE)',
        'Small Business Corp (Subchapter S)',
        'Disregarded Entity (Schedule C)'
      ],
      defaultProfile: {
        legalName: 'FlezPay Inc.',
        tradingName: 'FlezPay Global',
        regNumber: 'DE-7291048',
        tin: '84-2918402',
        businessType: 'C-Corporation',
        industry: 'Software & Financial Technology',
        country: 'US',
        state: 'Delaware (Division of Corporations)',
        city: 'Wilmington',
        address: '1209 North Orange Street',
        postalCode: '19801',
        email: 'tax-us@flezpay.com',
        phone: '+1 (302) 555-0194',
        jurisdiction: 'Delaware (Division of Corporations)',
        taxRegNumber: '84-2918402',
        vatNumber: 'ST-9876543-US',
        filingFrequency: 'Quarterly Estimated (Form 1120-W / 1040-ES)',
        fiscalYearStart: '01-01',
        fiscalYearEnd: '12-31',
        taxEntityType: 'C-Corporation',
        taxResidency: 'United States Domestic Corporation',
        taxRegime: 'Federal Corporate Income Tax (21%)'
      }
    },
    UK: {
      code: 'UK',
      name: 'United Kingdom',
      currency: '£',
      currencyCode: 'GBP',
      taxAuthority: 'HM Revenue & Customs (HMRC)',
      taxIdLabel: 'Unique Taxpayer Reference (UTR) / CRN',
      taxIdPlaceholder: 'e.g. 12345 67890',
      taxIdMask: '••••• 67890',
      vatLabel: 'UK VAT Registration Number',
      vatPlaceholder: 'e.g. GB 982 3410 82',
      businessRegistrationLabel: 'Companies House Company Number',
      businessRegistrationPlaceholder: 'e.g. 13892041',
      supportedTaxTypes: [
        'Private Limited Company (Ltd)',
        'Public Limited Company (PLC)',
        'Limited Liability Partnership (LLP)',
        'Sole Trader'
      ],
      jurisdictions: [
        'England and Wales (Companies House)',
        'Scotland',
        'Northern Ireland'
      ],
      filingPeriods: [
        'Quarterly Making Tax Digital (MTD) VAT',
        'Annual Corporation Tax (CT600)',
        'Monthly Real Time Information (RTI PAYE)'
      ],
      taxRegimes: [
        'Main Corporation Tax Rate (25%)',
        'Small Profits Rate (19% for Profits < £50k)',
        'Marginal Relief Scheme'
      ],
      defaultProfile: {
        legalName: 'FlezPay UK Ltd',
        tradingName: 'FlezPay Europe',
        regNumber: '13892041',
        tin: '91823 48102',
        businessType: 'Private Limited Company (Ltd)',
        industry: 'Fintech / Payment Intermediary',
        country: 'UK',
        state: 'England and Wales (Companies House)',
        city: 'London',
        address: '25 Bank Street, Canary Wharf',
        postalCode: 'E14 5JP',
        email: 'tax-uk@flezpay.com',
        phone: '+44 20 7946 0912',
        jurisdiction: 'England and Wales (Companies House)',
        taxRegNumber: '91823 48102',
        vatNumber: 'GB 982 3410 82',
        filingFrequency: 'Quarterly Making Tax Digital (MTD) VAT',
        fiscalYearStart: '04-06',
        fiscalYearEnd: '04-05',
        taxEntityType: 'Private Limited Company (Ltd)',
        taxResidency: 'United Kingdom Tax Resident',
        taxRegime: 'Main Corporation Tax Rate (25%)'
      }
    },
    DE: {
      code: 'DE',
      name: 'Germany',
      currency: '€',
      currencyCode: 'EUR',
      taxAuthority: 'Bundeszentralamt für Steuern (BZSt)',
      taxIdLabel: 'Steuernummer / Wirtschafts-Identifikationsnummer',
      taxIdPlaceholder: 'e.g. 12/345/67890',
      taxIdMask: '••/•••/67890',
      vatLabel: 'Umsatzsteuer-Identifikationsnummer (USt-IdNr)',
      vatPlaceholder: 'e.g. DE 123456789',
      businessRegistrationLabel: 'Handelsregisternummer (HRB)',
      businessRegistrationPlaceholder: 'e.g. HRB 92841 B',
      supportedTaxTypes: [
        'Gesellschaft mit beschränkter Haftung (GmbH)',
        'Unternehmergesellschaft (UG haftungsbeschränkt)',
        'Aktiengesellschaft (AG)',
        'Einzelunternehmen'
      ],
      jurisdictions: [
        'Finanzamt Berlin Mitte',
        'Finanzamt München',
        'Finanzamt Frankfurt am Main',
        'Finanzamt Hamburg-Mitte'
      ],
      filingPeriods: [
        'Monatliche Umsatzsteuer-Voranmeldung (USt-VA)',
        'Vierteljährliche Vorauszahlung',
        'Jährliche Körperschaftsteuererklärung'
      ],
      taxRegimes: [
        'Körperschaftsteuer (15% + 5.5% Soli)',
        'Gewerbesteuer (lokaler Hebesatz)',
        'Kleinunternehmerregelung (§ 19 UStG)'
      ],
      defaultProfile: {
        legalName: 'FlezPay Germany GmbH',
        tradingName: 'FlezPay DACH',
        regNumber: 'HRB 92841 B',
        tin: '27/614/09124',
        businessType: 'Gesellschaft mit beschränkter Haftung (GmbH)',
        industry: 'Finanzdienstleistungen & Software',
        country: 'DE',
        state: 'Finanzamt Berlin Mitte',
        city: 'Berlin',
        address: 'Friedrichstraße 176',
        postalCode: '10117',
        email: 'steuern-de@flezpay.com',
        phone: '+49 30 12345678',
        jurisdiction: 'Finanzamt Berlin Mitte',
        taxRegNumber: '27/614/09124',
        vatNumber: 'DE 948102834',
        filingFrequency: 'Monatliche Umsatzsteuer-Voranmeldung (USt-VA)',
        fiscalYearStart: '01-01',
        fiscalYearEnd: '12-31',
        taxEntityType: 'Gesellschaft mit beschränkter Haftung (GmbH)',
        taxResidency: 'Deutschland Unbeschränkt Steuerpflichtig',
        taxRegime: 'Körperschaftsteuer (15% + 5.5% Soli)'
      }
    },
    FR: {
      code: 'FR',
      name: 'France',
      currency: '€',
      currencyCode: 'EUR',
      taxAuthority: 'Direction Générale des Finances Publiques (DGFiP)',
      taxIdLabel: 'Numéro SIREN / SIRET',
      taxIdPlaceholder: 'e.g. 123 456 789 00012',
      taxIdMask: '••• ••• ••• 00012',
      vatLabel: 'Numéro de TVA Intracommunautaire',
      vatPlaceholder: 'e.g. FR 12 123456789',
      businessRegistrationLabel: 'Numéro RCS (Registre du Commerce)',
      businessRegistrationPlaceholder: 'e.g. RCS Paris B 123 456 789',
      supportedTaxTypes: [
        'Société par Actions Simplifiée (SAS)',
        'Société à Responsabilité Limitée (SARL)',
        'Société Anonyme (SA)',
        'Micro-entreprise'
      ],
      jurisdictions: [
        'Service des Impôts des Entreprises (SIE Paris Centre)',
        'SIE Lyon Est',
        'SIE Marseille',
        'SIE Bordeaux'
      ],
      filingPeriods: [
        'Mensuelle Déclaration CA3 (TVA)',
        'Trimestrielle (Régime Simplifié)',
        'Annuelle Déclaration 2065 (Impôt sur les Sociétés)'
      ],
      taxRegimes: [
        'Régime Réel Normal (IS 25%)',
        'Taux Réduit PME (15% jusqu\'à 42 500 €)',
        'Régime Simplifié d\'Imposition'
      ],
      defaultProfile: {
        legalName: 'FlezPay France SAS',
        tradingName: 'FlezPay France',
        regNumber: 'RCS Paris B 891 024 192',
        tin: '891 024 192 00018',
        businessType: 'Société par Actions Simplifiée (SAS)',
        industry: 'Technologies Financières',
        country: 'FR',
        state: 'Service des Impôts des Entreprises (SIE Paris Centre)',
        city: 'Paris',
        address: '14 Rue de la Paix',
        postalCode: '75002',
        email: 'fiscalite-fr@flezpay.com',
        phone: '+33 1 42 68 50 00',
        jurisdiction: 'Service des Impôts des Entreprises (SIE Paris Centre)',
        taxRegNumber: '891 024 192 00018',
        vatNumber: 'FR 34 891024192',
        filingFrequency: 'Mensuelle Déclaration CA3 (TVA)',
        fiscalYearStart: '01-01',
        fiscalYearEnd: '12-31',
        taxEntityType: 'Société par Actions Simplifiée (SAS)',
        taxResidency: 'Résident Fiscal Français',
        taxRegime: 'Régime Réel Normal (IS 25%)'
      }
    },
    CA: {
      code: 'CA',
      name: 'Canada',
      currency: '$',
      currencyCode: 'CAD',
      taxAuthority: 'Canada Revenue Agency (CRA) / ARC',
      taxIdLabel: 'Business Number (BN9 / Program Account)',
      taxIdPlaceholder: 'e.g. 123456789 RC 0001',
      taxIdMask: '•••••6789 RC 0001',
      vatLabel: 'GST/HST Account Number',
      vatPlaceholder: 'e.g. 123456789 RT 0001',
      businessRegistrationLabel: 'Corporation Registration Number',
      businessRegistrationPlaceholder: 'e.g. BC-1294801',
      supportedTaxTypes: [
        'Federal Corporation (Inc./Ltd.)',
        'Provincial Corporation',
        'Sole Proprietorship',
        'General Partnership'
      ],
      jurisdictions: [
        'Ontario (Ministry of Finance)',
        'British Columbia (Ministry of Finance)',
        'Quebec (Revenu Québec)',
        'Alberta (Tax and Revenue Administration)'
      ],
      filingPeriods: [
        'Quarterly Remittance (GST/HST NETFILE)',
        'Annual Corporate Return (T2)',
        'Monthly Source Deductions (Payroll)'
      ],
      taxRegimes: [
        'Small Business Deduction (9% Fed + Prov)',
        'General Corporate Tax Rate (15% Fed + Prov)',
        'Canadian-Controlled Private Corp (CCPC)'
      ],
      defaultProfile: {
        legalName: 'FlezPay Canada Ltd',
        tradingName: 'FlezPay North America',
        regNumber: 'BC-1294801',
        tin: '849201948 RC 0001',
        businessType: 'Federal Corporation (Inc./Ltd.)',
        industry: 'Fintech & Merchant Payments',
        country: 'CA',
        state: 'Ontario (Ministry of Finance)',
        city: 'Toronto',
        address: '100 King Street West, Suite 5600',
        postalCode: 'M5X 1C9',
        email: 'tax-ca@flezpay.com',
        phone: '+1 (416) 555-0178',
        jurisdiction: 'Ontario (Ministry of Finance)',
        taxRegNumber: '849201948 RC 0001',
        vatNumber: '849201948 RT 0001',
        filingFrequency: 'Quarterly Remittance (GST/HST NETFILE)',
        fiscalYearStart: '01-01',
        fiscalYearEnd: '12-31',
        taxEntityType: 'Federal Corporation (Inc./Ltd.)',
        taxResidency: 'Canadian Tax Resident (CCPC)',
        taxRegime: 'Small Business Deduction (9% Fed + Prov)'
      }
    }
  };

  // -------------------------------------------------------------------------
  // 2. TAX SERVICE (Mock Implementation with API-ready hooks)
  // -------------------------------------------------------------------------
  const TaxService = {
    /**
     * Get all supported country configurations.
     */
    async getCountryConfigs() {
      await delay(100);
      return COUNTRY_CONFIGS;
    },

    /**
     * Get configuration for a specific country code.
     */
    async getCountryConfig(countryCode) {
      await delay(80);
      let defaultCode = 'NG';
      if (typeof window !== 'undefined' && window.STORE_CURRENCY_CODE) {
        const c = window.STORE_CURRENCY_CODE.toUpperCase();
        if (c === 'USD') defaultCode = 'US';
        else if (c === 'GBP') defaultCode = 'UK';
        else if (c === 'EUR') defaultCode = 'DE';
        else if (c === 'CAD') defaultCode = 'CA';
        else if (c === 'NGN') defaultCode = 'NG';
      }
      const code = (countryCode || defaultCode).toUpperCase();
      return COUNTRY_CONFIGS[code] || COUNTRY_CONFIGS[defaultCode] || COUNTRY_CONFIGS.NG;
    },

    /**
     * Retrieve the business tax profile.
     * /* TODO: Replace with GET /api/v1/tax/profile when tax engine API is connected * /
     */
    async getTaxProfile() {
      await delay(200);
      const stored = localStorage.getItem(STORAGE_KEYS.TAX_PROFILE);
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch (e) {
          console.warn('TaxService: Failed parsing stored profile, using default.');
        }
      }
      // Default initial mock profile based on user's currency/store region
      let defaultCountry = 'NG';
      if (typeof window !== 'undefined' && window.STORE_CURRENCY_CODE) {
        const cCode = window.STORE_CURRENCY_CODE.toUpperCase();
        if (cCode === 'USD') defaultCountry = 'US';
        else if (cCode === 'GBP') defaultCountry = 'UK';
        else if (cCode === 'EUR') defaultCountry = 'DE';
        else if (cCode === 'CAD') defaultCountry = 'CA';
        else if (cCode === 'NGN') defaultCountry = 'NG';
      }
      const defaultProfile = { ...(COUNTRY_CONFIGS[defaultCountry] || COUNTRY_CONFIGS.NG).defaultProfile };
      localStorage.setItem(STORAGE_KEYS.TAX_PROFILE, JSON.stringify(defaultProfile));
      return defaultProfile;
    },

    /**
     * Update the business tax profile.
     * /* TODO: Replace with PUT /api/v1/tax/profile when tax engine API is connected * /
     */
    async updateTaxProfile(profileData) {
      await delay(350);
      if (!profileData || typeof profileData !== 'object') {
        throw new Error('Invalid tax profile payload.');
      }
      // Security: never log raw tax ID or sensitive fields to console
      const sanitized = { ...profileData, updatedAt: new Date().toISOString() };
      localStorage.setItem(STORAGE_KEYS.TAX_PROFILE, JSON.stringify(sanitized));
      return sanitized;
    },

    /**
     * Retrieve the high-level estimated financial overview.
     * /* TODO: Replace with GET /api/v1/tax/overview * /
     */
    async getTaxOverview() {
      await delay(180);
      const cur = getUserCurrency();
      return {
        estimatedTaxableIncome: 0.00,
        estimatedTaxLiability: 0.00,
        deductibleExpenses: 0.00,
        taxDocumentsCollected: 24,
        taxDocumentsRequired: 27,
        effectiveTaxRate: 0.00,
        currencySymbol: cur,
        isMockData: true,
        periodLabel: 'FY 2026 (Q1 - Q3 YTD)'
      };
    },

    /**
     * Retrieve the current tax filing status and progress timeline.
     * /* TODO: Replace with GET /api/v1/tax/filing-status * /
     */
    async getFilingStatus() {
      await delay(220);
      return {
        taxYear: 2026,
        statusText: 'Preparation in progress',
        statusCode: 'IN_PREPARATION',
        lastSynchronized: 'Today, 10:42 AM',
        transactionsAnalyzed: 1248,
        documentsCollected: 24,
        documentsTotal: 27,
        timeline: [
          { stage: 'Tax profile completed', status: 'completed', icon: 'check-circle' },
          { stage: 'Financial data synchronized', status: 'completed', icon: 'check-circle' },
          { stage: 'Transactions categorized', status: 'completed', icon: 'check-circle' },
          { stage: 'Tax preparation', status: 'active', icon: 'clock' },
          { stage: 'Compliance review', status: 'pending', icon: 'circle' },
          { stage: 'Official filing', status: 'pending', icon: 'circle' }
        ]
      };
    },

    /**
     * Retrieve detailed mock filing summary for review modal.
     * /* TODO: Replace with GET /api/v1/tax/filing-summary * /
     */
    async getFilingSummary() {
      await delay(250);
      const cur = getUserCurrency();
      return {
        taxYear: 2026,
        preparedFor: 'FlezPay Enterprise',
        entityType: 'Operating Entity',
        grossRevenue: 0.00,
        costOfGoods: 0.00,
        operatingExpenses: 0.00,
        netTaxableIncome: 0.00,
        federalEstimatedRate: 0.0,
        stateEstimatedRate: 0.0,
        totalEstimatedTaxDue: 0.00,
        prepaidCredits: 0.00,
        balanceRemaining: 0.00,
        currencySymbol: cur,
        dueDate: 'October 15, 2026',
        filingMethod: 'Electronic Regulatory Return',
        disclaimer: 'Demonstration estimate generated by FlezPay Intelligence. Not an official tax return submission.'
      };
    },

    /**
     * Retrieve tax document checklist and verification records.
     * /* TODO: Replace with GET /api/v1/tax/documents * /
     */
    async getTaxDocuments() {
      await delay(200);
      const stored = localStorage.getItem(STORAGE_KEYS.TAX_DOCUMENTS);
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch (e) {}
      }

      const defaultDocs = [
        { id: 'doc-1', name: 'Invoice records', type: 'Sales & Invoicing', date: 'Sep 08, 2026', status: 'Verified', verified: true, count: '384 files' },
        { id: 'doc-2', name: 'Expense records & receipts', type: 'Purchasing', date: 'Sep 07, 2026', status: 'Verified', verified: true, count: '148 receipts' },
        { id: 'doc-3', name: 'Commercial bank statements', type: 'Banking', date: 'Sep 05, 2026', status: 'Verified', verified: true, count: '8 statements' },
        { id: 'doc-4', name: 'Payroll & wage disbursement records', type: 'Payroll', date: 'Sep 02, 2026', status: 'Verified', verified: true, count: '12 pay runs' },
        { id: 'doc-5', name: 'State / Federal Tax registration certificates', type: 'Legal', date: 'Aug 14, 2026', status: 'Verified', verified: true, count: '2 documents' },
        { id: 'doc-6', name: 'Annual financial statement & trial balance', type: 'Accounting', date: 'Pending', status: 'Pending upload', verified: false, count: 'Awaiting doc' }
      ];

      localStorage.setItem(STORAGE_KEYS.TAX_DOCUMENTS, JSON.stringify(defaultDocs));
      return defaultDocs;
    },

    /**
     * Simulate uploading a document into the compliance repository.
     * /* TODO: Replace with POST /api/v1/tax/documents/upload * /
     */
    async uploadTaxDocument(fileMeta) {
      await delay(600);
      const docs = await this.getTaxDocuments();
      const newDoc = {
        id: 'doc-' + Date.now(),
        name: fileMeta.name || 'Uploaded Financial Document.pdf',
        type: fileMeta.type || 'Supplementary Evidence',
        date: 'Just now',
        status: 'Verified',
        verified: true,
        count: '1 file (' + (fileMeta.size || '1.8 MB') + ')'
      };
      docs.unshift(newDoc);
      localStorage.setItem(STORAGE_KEYS.TAX_DOCUMENTS, JSON.stringify(docs));
      return newDoc;
    },

    /**
     * Retrieve intelligent AI tax insights and deductions.
     * /* TODO: Replace with GET /api/v1/tax/insights * /
     */
    async getTaxInsights() {
      await delay(220);
      const stored = localStorage.getItem(STORAGE_KEYS.TAX_INSIGHTS);
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch (e) {}
      }

      const cur = getUserCurrency();
      const defaultInsights = [
        {
          id: 'insight-1',
          type: 'deduction',
          title: 'Potential deductible expense',
          amount: 0.00,
          description: `Identified eligible recurring operational expense write-off opportunities in your synchronized accounts.`,
          status: 'action_required',
          actionLabel: 'Apply deduction'
        },
        {
          id: 'insight-2',
          type: 'missing_docs',
          title: 'Missing documentation',
          amount: null,
          transactionsCount: 3,
          description: '3 outgoing vendor transactions require invoice receipts for compliance verification and audit readiness.',
          status: 'action_required',
          actionLabel: 'Attach receipts'
        },
        {
          id: 'insight-3',
          type: 'classification',
          title: 'Potential tax classification issue',
          amount: null,
          transactionsCount: 2,
          description: '2 vendor service payments were categorized as general office supplies. Reclassifying prevents misreporting on statutory returns.',
          status: 'action_required',
          actionLabel: 'Reclassify transactions'
        }
      ];

      localStorage.setItem(STORAGE_KEYS.TAX_INSIGHTS, JSON.stringify(defaultInsights));
      return defaultInsights;
    },

    /**
     * Resolve or apply an AI tax insight.
     * /* TODO: Replace with POST /api/v1/tax/insights/:id/resolve * /
     */
    async resolveTaxInsight(insightId) {
      await delay(300);
      const insights = await this.getTaxInsights();
      const updated = insights.map(item => {
        if (item.id === insightId) {
          return { ...item, status: 'resolved' };
        }
        return item;
      });
      localStorage.setItem(STORAGE_KEYS.TAX_INSIGHTS, JSON.stringify(updated));
      return updated;
    },

    /**
     * Retrieve Tax Settings (Real-time invoicing & Autonomous Filing).
     * /* TODO: Replace with GET /api/v1/tax/settings * /
     */
    async getTaxSettings() {
      await delay(150);
      const stored = localStorage.getItem(STORAGE_KEYS.TAX_SETTINGS);
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch (e) {}
      }
      const defaultSettings = {
        realtimeInvoicing: true,
        autonomousTaxFiling: false,
        authorizationLevel: 'prepare_approval' // 'prepare_only' | 'prepare_approval' | 'fully_autonomous'
      };
      localStorage.setItem(STORAGE_KEYS.TAX_SETTINGS, JSON.stringify(defaultSettings));
      return defaultSettings;
    },

    /**
     * Update Tax Settings.
     * /* TODO: Replace with PUT /api/v1/tax/settings * /
     */
    async updateTaxSettings(newSettings) {
      await delay(250);
      const current = await this.getTaxSettings();
      const updated = { ...current, ...newSettings };
      localStorage.setItem(STORAGE_KEYS.TAX_SETTINGS, JSON.stringify(updated));
      return updated;
    }
  };

  // -------------------------------------------------------------------------
  // 3. CREDIT SERVICE (Mock Implementation with API-ready hooks)
  // -------------------------------------------------------------------------
  const CreditService = {
    /**
     * Retrieve the business credit health overview and score.
     * /* TODO: Replace with GET /api/v1/credit/overview * /
     */
    async getCreditOverview() {
      await delay(220);
      return {
        score: 682,
        maxScore: 850,
        minScore: 300,
        rating: 'Good',
        changePeriod: 'this quarter',
        changePoints: 24,
        changeDirection: 'up',
        lastUpdated: 'September 9, 2026',
        isMockScore: true,
        summaryFactors: {
          paymentHistory: { rating: 'Excellent', score: '98%', status: 'good' },
          creditUtilization: { rating: 'Optimal', score: '0%', status: 'good' },
          creditAge: { rating: 'Good', score: '5.2 years', status: 'good' },
          creditMix: { rating: 'Fair', score: '3 types', status: 'neutral' },
          newApplications: { rating: 'Excellent', score: '1 inquiry', status: 'good' }
        }
      };
    },

    /**
     * Retrieve detailed credit factors and breakdown metrics.
     * /* TODO: Replace with GET /api/v1/credit/factors * /
     */
    async getCreditFactors() {
      await delay(200);
      return [
        {
          key: 'payment_history',
          name: 'Payment History',
          rating: 'Excellent',
          value: '98%',
          impact: 'High Impact',
          statusClass: 'emerald',
          progressBar: 98,
          description: '48 out of 49 on-time trade payments over the past 24 months. Consistency strongly supports business creditworthiness.'
        },
        {
          key: 'credit_utilization',
          name: 'Credit Utilization',
          rating: 'Optimal',
          value: '0%',
          impact: 'High Impact',
          statusClass: 'emerald',
          progressBar: 5,
          description: `${getUserCurrency()}0.00 balance across ${getUserCurrency()}0.00 total revolving limits. Keeping utilization low optimizes borrowing potential.`
        },
        {
          key: 'credit_age',
          name: 'Credit Age',
          rating: 'Good',
          value: '5.2 years',
          impact: 'Medium Impact',
          statusClass: 'emerald',
          progressBar: 65,
          description: 'Average commercial credit history length is 5.2 years. Your oldest active line was established 8.4 years ago.'
        },
        {
          key: 'credit_mix',
          name: 'Credit Mix',
          rating: 'Fair',
          value: '3 account types',
          impact: 'Low Impact',
          statusClass: 'indigo',
          progressBar: 60,
          description: 'Portfolio includes 2 revolving cards and 1 commercial installment loan. Adding an equipment trade line can broaden your mix.'
        },
        {
          key: 'recent_applications',
          name: 'Recent Inquiries',
          rating: 'Excellent',
          value: '1 inquiry',
          impact: 'Low Impact',
          statusClass: 'emerald',
          progressBar: 90,
          description: 'Only 1 hard credit inquiry recorded in the last 12 months. Low application activity prevents score drag.'
        }
      ];
    },

    /**
     * Retrieve priority AI credit optimization recommendations.
     * /* TODO: Replace with GET /api/v1/credit/recommendations * /
     */
    async getCreditInsights() {
      await delay(200);
      const cur = getUserCurrency();
      return [
        {
          id: 'act-1',
          number: '01',
          title: 'Reduce credit utilization',
          badge: 'High Impact',
          currentMetric: 'Your utilization is currently 0%.',
          recommendedAction: `Revolving balances are at ${cur}0.00. Maintain low utilization to sustain high creditworthiness.`,
          potentialBenefit: 'Low utilization preserves pristine credit health and optimizes borrowing terms.',
          buttonText: 'View plan',
          targetView: 'action_plan'
        },
        {
          id: 'act-2',
          number: '02',
          title: 'Upcoming scheduled payment',
          badge: 'Due in 3 days',
          currentMetric: 'Commercial Card payment due September 12, 2026.',
          recommendedAction: `Amount: ${cur}0.00 minimum payment (${cur}0.00 recommended statement clearance).`,
          potentialBenefit: 'Preserves your 98% on-time payment track record.',
          buttonText: 'Review payment',
          targetView: 'payment_review'
        },
        {
          id: 'act-3',
          number: '03',
          title: 'Credit report issue detected',
          badge: 'Discrepancy',
          currentMetric: 'Continuous ledger reconciliation active across connected accounts.',
          recommendedAction: `Account shows ${cur}0.00 balance vs ${cur}0.00 recorded in FlezPay ledger.`,
          potentialBenefit: 'Disputing inaccurate balances immediately protects reported utilization.',
          buttonText: 'Review issue',
          targetView: 'dispute_review'
        }
      ];
    },

    /**
     * Retrieve the interactive 90-Day Credit Action Plan.
     * /* TODO: Replace with GET /api/v1/credit/action-plan * /
     */
    async getCreditActionPlan() {
      await delay(180);
      const stored = localStorage.getItem(STORAGE_KEYS.CREDIT_PLAN);
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch (e) {}
      }

      const cur = getUserCurrency();
      const defaultPlan = {
        completionPercentage: 40,
        items: [
          { id: 'plan-1', week: 'Week 1', title: 'Review credit report', completed: true, desc: 'Audit commercial credit profiles across all reporting bureaus.' },
          { id: 'plan-2', week: 'Week 2', title: 'Reduce revolving utilization', completed: true, desc: `Maintain low revolving credit line balances at ${cur}0.00 to preserve zero credit drag.` },
          { id: 'plan-3', week: 'Week 4', title: 'Maintain payment schedule', completed: false, desc: 'Ensure all upcoming recurring vendor and card payments process on time.' },
          { id: 'plan-4', week: 'Week 8', title: 'Review credit utilization again', completed: false, desc: 'Verify statement balances have dropped to target threshold (<35%).' },
          { id: 'plan-5', week: 'Week 12', title: 'Reassess credit health', completed: false, desc: 'Request updated soft-pull score and evaluate credit line expansion.' }
        ]
      };

      localStorage.setItem(STORAGE_KEYS.CREDIT_PLAN, JSON.stringify(defaultPlan));
      return defaultPlan;
    },

    /**
     * Toggle action item completion status.
     * /* TODO: Replace with PUT /api/v1/credit/action-plan/:id * /
     */
    async toggleActionPlanItem(itemId) {
      await delay(150);
      const plan = await this.getCreditActionPlan();
      plan.items = plan.items.map(item => {
        if (item.id === itemId) {
          return { ...item, completed: !item.completed };
        }
        return item;
      });

      // Calculate new completion percentage
      const completedCount = plan.items.filter(i => i.completed).length;
      plan.completionPercentage = Math.round((completedCount / plan.items.length) * 100);

      localStorage.setItem(STORAGE_KEYS.CREDIT_PLAN, JSON.stringify(plan));
      return plan;
    },

    /**
     * Retrieve reported commercial credit accounts.
     * /* TODO: Replace with GET /api/v1/credit/accounts * /
     */
    async getCreditAccounts() {
      await delay(200);
      const cur = getUserCurrency();
      return {
        totalBalance: 0.00,
        totalRevolvingLimit: 0.00,
        revolvingUtilization: 0.0,
        lastUpdated: 'September 9, 2026',
        accounts: [
          {
            id: 'acc-1',
            name: 'Credit Card A (Commercial Card)',
            balance: 0.00,
            limit: 0.00,
            utilization: '0%',
            type: 'Revolving Line',
            status: 'Good standing',
            statusClass: 'emerald',
            lastPayment: `Aug 28, 2026 (${cur}0.00)`
          },
          {
            id: 'acc-2',
            name: 'Credit Card B (Commercial Card)',
            balance: 0.00,
            limit: 0.00,
            utilization: '0%',
            type: 'Revolving Line',
            status: 'Current',
            statusClass: 'emerald',
            lastPayment: `Aug 14, 2026 (${cur}0.00)`
          },
          {
            id: 'acc-3',
            name: 'Commercial Installment Facility',
            balance: 0.00,
            limit: null,
            utilization: '—',
            type: 'Installment Loan',
            status: 'Current',
            statusClass: 'emerald',
            lastPayment: `Sep 01, 2026 (${cur}0.00)`
          }
        ]
      };
    },

    /**
     * Retrieve detected credit discrepancies.
     * /* TODO: Replace with GET /api/v1/credit/issues * /
     */
    async getCreditIssues() {
      await delay(180);
      const stored = localStorage.getItem(STORAGE_KEYS.CREDIT_ISSUES);
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch (e) {}
      }

      const defaultIssue = {
        id: 'issue-discrepancy-1',
        title: 'Potential reporting discrepancy',
        accountName: 'Credit Card B (Commercial Card)',
        reportedAmount: 0.00,
        connectedLedgerAmount: 0.00,
        difference: 0.00,
        status: 'detected', // 'detected' | 'disputed'
        detectedDate: 'September 08, 2026',
        explanation: 'FlezPay ledger verifies account reconciliation with zero unexplained discrepancy.',
        evidenceTransactions: [
          { id: 'tx-891', date: 'Aug 28, 2026', desc: 'Electronic Autopay Reconciliation', amount: 0.00, status: 'Cleared' }
        ]
      };

      localStorage.setItem(STORAGE_KEYS.CREDIT_ISSUES, JSON.stringify(defaultIssue));
      return defaultIssue;
    },

    /**
     * Submit a mock credit dispute package.
     * /* TODO: Replace with POST /api/v1/credit/disputes * /
     */
    async submitCreditDispute(issueId, disputeData) {
      await delay(600);
      const issue = await this.getCreditIssues();
      const updated = {
        ...issue,
        status: 'disputed',
        disputeReference: 'DISP-' + Math.floor(100000 + Math.random() * 900000),
        disputeSubmittedAt: new Date().toISOString(),
        disputeReason: disputeData.reason || 'Payment cleared prior to bureau statement cutoff date'
      };
      localStorage.setItem(STORAGE_KEYS.CREDIT_ISSUES, JSON.stringify(updated));
      return updated;
    }
  };

  // -------------------------------------------------------------------------
  // 4. FINANCIAL AGENT SERVICE (Autonomous actions & permissions)
  // -------------------------------------------------------------------------
  const FinancialAgentService = {
    /**
     * Retrieve financial agent automation settings.
     * /* TODO: Replace with GET /api/v1/financial-agent/settings * /
     */
    async getSettings() {
      await delay(160);
      const stored = localStorage.getItem(STORAGE_KEYS.AGENT_SETTINGS);
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch (e) {}
      }

      const defaultAgentSettings = {
        paymentReminders: true,
        billOptimization: true,
        utilizationMonitoring: true,
        taxDeadlineMonitoring: true,
        taxPreparation: true,
        automaticPayments: false // High-risk action, disabled by default
      };

      localStorage.setItem(STORAGE_KEYS.AGENT_SETTINGS, JSON.stringify(defaultAgentSettings));
      return defaultAgentSettings;
    },

    /**
     * Update financial agent automation settings.
     * /* TODO: Replace with PUT /api/v1/financial-agent/settings * /
     */
    async updateSettings(newSettings) {
      await delay(250);
      const current = await this.getSettings();
      const updated = { ...current, ...newSettings };
      localStorage.setItem(STORAGE_KEYS.AGENT_SETTINGS, JSON.stringify(updated));
      return updated;
    }
  };

  // -------------------------------------------------------------------------
  // 5. AI ADVISOR SERVICE (Tax & Credit Financial Intelligence)
  // -------------------------------------------------------------------------
  const AIService = {
    /**
     * Answer questions regarding tax compliance, credit score optimization,
     * filing timelines, deductions, utilization, and financial agent capabilities.
     * /* TODO: Connect to backend LLM / agent endpoint POST /api/v1/tax-credit/ai-ask * /
     */
    async askAI({ question, context = 'all' }) {
      await delay(450); // Natural simulated thinking delay

      const q = (question || '').toLowerCase();

      const cur = getUserCurrency();

      // Tax: Section 179 / Deductions
      if (q.includes('179') || q.includes('deduct') || q.includes('write-off') || q.includes('expense')) {
        return {
          category: 'tax',
          answer: `Based on your synchronized FY 2026 ledger, FlezPay Intelligence identified **${cur}0.00 in deductible expenses**, including qualifying operational expense write-offs. Your current estimated taxable base is **${cur}0.00** with **${cur}0.00** in immediate liability.`
        };
      }

      // Tax: Liability / Income / Effective Rate / Owe
      if (q.includes('liability') || q.includes('taxable income') || q.includes('how much tax') || q.includes('owe') || q.includes('effective rate')) {
        return {
          category: 'tax',
          answer: `Your estimated taxable income is **${cur}0.00** with an estimated tax liability of **${cur}0.00** (~0% effective tax rate). After factoring in prepaid tax credits of ${cur}0.00, your current remaining net estimated balance is **${cur}0.00**.`
        };
      }

      // Tax: Filing deadline / timeline / status
      if (q.includes('deadline') || q.includes('due') || q.includes('when') || q.includes('timeline') || q.includes('status') || q.includes('filing')) {
        return {
          category: 'tax',
          answer: `Your 2026 Q3 filing status is currently **Preparation in progress**. FlezPay has analyzed 1,248 transactions and collected 24 of 27 required documents (89% complete). Your official filing window opens on October 15, 2026.`
        };
      }

      // Tax: Documents / Receipts / Missing
      if (q.includes('doc') || q.includes('receipt') || q.includes('w-2') || q.includes('1099') || q.includes('audit')) {
        return {
          category: 'tax',
          answer: `You currently have **24 verified documents** on file in your Document Center. However, FlezPay Intelligence flagged **3 missing vendor receipts** for outgoing transactions. Uploading these via the Document Center will prevent audit flags and secure full compliance.`
        };
      }

      // Tax: Profile / Country / TIN / EIN / VAT
      if (q.includes('tin') || q.includes('ein') || q.includes('country') || q.includes('vat') || q.includes('utr') || q.includes('profile')) {
        return {
          category: 'tax',
          answer: `Your Tax Profile supports multi-jurisdiction compliance across Nigeria (TIN), US (EIN), UK (UTR), Germany (Steuernummer), France (SIREN), and Canada (BN). Your identification numbers are stored securely with end-to-end masking.`
        };
      }

      // Credit: Score calculation & rating
      if (q.includes('score') || q.includes('682') || q.includes('good') || q.includes('rating') || q.includes('gauge')) {
        return {
          category: 'credit',
          answer: `Your commercial credit score is **682 (Good)**, up **+24 points** this quarter. Your score is driven by strong 98% payment history, a 5.2-year account age, and **0% credit utilization** across revolving credit lines.`
        };
      }

      // Credit: Utilization & lowering
      if (q.includes('utiliz') || q.includes('limit') || q.includes('balance') || q.includes('card')) {
        return {
          category: 'credit',
          answer: `Your aggregate credit utilization is **0%** (${cur}0.00 used out of ${cur}0.00 total limits). Maintaining utilization below 30% preserves maximum borrowing potential.`
        };
      }

      // Credit: Action Plan / 90-day / milestones
      if (q.includes('plan') || q.includes('90-day') || q.includes('milestone') || q.includes('goal') || q.includes('720')) {
        return {
          category: 'credit',
          answer: `You are **40% complete** with your 90-Day Credit Plan toward a target score of **720+**. Completed: setup automated reminders & verified account limits. Next up: maintain zero revolving balances.`
        };
      }

      // Credit: Dispute / bureau / discrepancy
      if (q.includes('dispute') || q.includes('issue') || q.includes('bureau') || q.includes('discrepancy') || q.includes('card b')) {
        return {
          category: 'credit',
          answer: `FlezPay ledger records reflect ${cur}0.00 in outstanding discrepancies against bureau reports. In the *Disputes & Issues* tab, you can review reporting details and initiate resolution packets if needed.`
        };
      }

      // Financial Agent / Automation / Autopay
      if (q.includes('agent') || q.includes('auto') || q.includes('autopay') || q.includes('permission') || q.includes('reminder')) {
        return {
          category: 'all',
          answer: `The FlezPay Financial Agent can automate payment reminders, statement bill optimization, real-time utilization alerts, and draft tax transaction categorization. Automated recurring payouts are gated behind high-risk multi-factor confirmation for enterprise safety.`
        };
      }

      // Fallback general response
      return {
        category: context,
        answer: `I have analyzed your FlezPay financial ecosystem. Your business is operating with **${cur}0.00** in taxable income, **${cur}0.00** in estimated tax liability, and a commercial credit health score of **682 (Good)**. Would you like actionable guidance on tax compliance, optimizing credit health, or preparing for tax filing?`
      };
    }
  };

  // Export to window
  window.TaxCreditService = {
    TaxService,
    CreditService,
    FinancialAgentService,
    AIService,
    COUNTRY_CONFIGS
  };

})(window);
