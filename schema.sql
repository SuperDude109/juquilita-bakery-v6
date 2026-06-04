PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('owner','manager','cashier','baker','decorator','wholesale_manager','admin','guest','premium','pending_premium')),
    business_name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    wholesale_tier TEXT DEFAULT 'retail',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    user_agent TEXT DEFAULT '',
    ip_address TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    was_successful INTEGER NOT NULL,
    attempted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'text',
    label TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS business_hours (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6),
    day_en TEXT NOT NULL,
    day_es TEXT NOT NULL,
    opens_at TEXT NOT NULL,
    closes_at TEXT NOT NULL,
    slot_capacity INTEGER NOT NULL DEFAULT 6,
    is_closed INTEGER NOT NULL DEFAULT 0,
    profile TEXT NOT NULL DEFAULT 'active',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS closures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    closure_date TEXT NOT NULL,
    reason TEXT NOT NULL,
    opens_at TEXT DEFAULT '',
    closes_at TEXT DEFAULT '',
    is_closed INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    key TEXT PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_es TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 100,
    description_en TEXT DEFAULT '',
    description_es TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name_es TEXT NOT NULL,
    name_en TEXT NOT NULL,
    category_key TEXT NOT NULL REFERENCES categories(key),
    subcategory TEXT DEFAULT '',
    description_es TEXT NOT NULL,
    description_en TEXT NOT NULL,
    base_price REAL,
    wholesale_price REAL,
    unit TEXT NOT NULL DEFAULT 'each',
    stock_count INTEGER NOT NULL DEFAULT 0,
    stock_policy TEXT NOT NULL CHECK(stock_policy IN ('track','made_to_order','quote','do_not_track')) DEFAULT 'track',
    lead_time_hours INTEGER NOT NULL DEFAULT 0,
    order_mode TEXT NOT NULL CHECK(order_mode IN ('order','quote','inactive')) DEFAULT 'order',
    is_featured INTEGER NOT NULL DEFAULT 0,
    is_bulk_friendly INTEGER NOT NULL DEFAULT 0,
    is_seasonal INTEGER NOT NULL DEFAULT 0,
    season_start TEXT DEFAULT '',
    season_end TEXT DEFAULT '',
    search_terms TEXT DEFAULT '',
    image_url TEXT DEFAULT '',
    image_alt TEXT DEFAULT '',
    canonical_key TEXT DEFAULT '',
    product_image_status TEXT DEFAULT 'needsOwnerPhoto',
    product_image_confidence TEXT DEFAULT 'low',
    product_image_filename TEXT DEFAULT '',
    product_image_source_url TEXT DEFAULT '',
    visual_tags TEXT DEFAULT '',
    visual_shape TEXT DEFAULT '',
    public_status TEXT NOT NULL DEFAULT 'public',
    public_notes TEXT DEFAULT '',
    image_accent TEXT DEFAULT 'marigold',
    icon TEXT DEFAULT '🥐',
    photo_status TEXT DEFAULT 'needs_real_photo',
    price_basis TEXT DEFAULT '',
    allergen_notes TEXT DEFAULT '',
    ingredient_notes TEXT DEFAULT '',
    margin_estimate REAL NOT NULL DEFAULT 0.58,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    variant_type TEXT NOT NULL,
    name_es TEXT NOT NULL,
    name_en TEXT NOT NULL,
    price_delta REAL NOT NULL DEFAULT 0,
    wholesale_delta REAL NOT NULL DEFAULT 0,
    is_default INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS bundles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name_en TEXT NOT NULL,
    name_es TEXT NOT NULL,
    description_en TEXT NOT NULL,
    description_es TEXT NOT NULL,
    items_json TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 100,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS promotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    discount_type TEXT NOT NULL CHECK(discount_type IN ('percent','fixed')),
    discount_value REAL NOT NULL,
    min_subtotal REAL NOT NULL DEFAULT 0,
    applies_to_role TEXT NOT NULL DEFAULT 'all',
    category_key TEXT NOT NULL DEFAULT 'all',
    starts_on TEXT NOT NULL,
    ends_on TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    max_redemptions INTEGER NOT NULL DEFAULT 0,
    per_customer_limit INTEGER NOT NULL DEFAULT 0,
    auto_apply INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promo_redemptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promotion_id INTEGER NOT NULL REFERENCES promotions(id),
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    customer_email TEXT NOT NULL,
    redeemed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_code TEXT UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    business_name TEXT DEFAULT '',
    customer_type TEXT NOT NULL DEFAULT 'guest',
    pickup_date TEXT NOT NULL,
    pickup_time TEXT NOT NULL,
    fulfillment TEXT NOT NULL DEFAULT 'pickup',
    payment_method TEXT NOT NULL DEFAULT 'pay_at_pickup',
    notes TEXT DEFAULT '',
    customer_language TEXT NOT NULL DEFAULT 'en',
    substitution_preference TEXT NOT NULL DEFAULT 'call_me',
    receipt_token TEXT DEFAULT '',
    cancellation_cutoff_at TEXT DEFAULT '',
    edit_cutoff_at TEXT DEFAULT '',
    pickup_shelf TEXT DEFAULT '',
    staff_notes TEXT DEFAULT '',
    subtotal REAL NOT NULL,
    discount REAL NOT NULL DEFAULT 0,
    tax REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL,
    deposit_due REAL NOT NULL DEFAULT 0,
    promo_code TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'received',
    status_reason TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    product_slug TEXT NOT NULL,
    product_name TEXT NOT NULL,
    unit_price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    variant_summary TEXT DEFAULT '',
    options_json TEXT DEFAULT '{}',
    line_total REAL NOT NULL,
    production_category TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS quote_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_code TEXT UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    business_name TEXT DEFAULT '',
    event_type TEXT DEFAULT '',
    event_date TEXT DEFAULT '',
    pickup_date TEXT DEFAULT '',
    pickup_time TEXT DEFAULT '',
    quantity INTEGER NOT NULL DEFAULT 1,
    budget TEXT DEFAULT '',
    flavor TEXT DEFAULT '',
    filling TEXT DEFAULT '',
    inscription TEXT DEFAULT '',
    style_notes TEXT DEFAULT '',
    reference_url TEXT DEFAULT '',
    reference_image_url TEXT DEFAULT '',
    complexity_tier TEXT DEFAULT '',
    servings INTEGER NOT NULL DEFAULT 0,
    colors TEXT DEFAULT '',
    exact_inscription_confirmed INTEGER NOT NULL DEFAULT 0,
    pickup_handling TEXT DEFAULT '',
    quote_public_token TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new',
    admin_estimate TEXT DEFAULT '',
    admin_notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wholesale_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    business_name TEXT NOT NULL,
    contact_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    business_type TEXT NOT NULL,
    expected_weekly_units INTEGER NOT NULL DEFAULT 0,
    requested_products TEXT DEFAULT '',
    delivery_or_pickup TEXT DEFAULT 'pickup',
    notes TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS standing_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    business_name TEXT NOT NULL,
    name TEXT NOT NULL,
    weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6),
    pickup_time TEXT NOT NULL,
    notes TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS standing_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standing_order_id INTEGER NOT NULL REFERENCES standing_orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    variant_summary TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    city TEXT NOT NULL,
    website TEXT DEFAULT '',
    contact_name TEXT DEFAULT '',
    contact_email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    story TEXT NOT NULL,
    highlight TEXT NOT NULL,
    consent_date TEXT DEFAULT '',
    approved_story_at TEXT DEFAULT '',
    rights_notes TEXT DEFAULT '',
    public_visible INTEGER NOT NULL DEFAULT 0,
    has_consent INTEGER NOT NULL DEFAULT 0,
    logo_url TEXT DEFAULT '',
    monthly_volume_estimate INTEGER NOT NULL DEFAULT 0,
    is_demo INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seasonal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    event_date TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    focus_categories TEXT NOT NULL,
    focus_products TEXT NOT NULL,
    demand_multiplier REAL NOT NULL DEFAULT 1.0,
    prep_notes TEXT NOT NULL,
    marketing_notes TEXT NOT NULL,
    labor_notes TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    change_qty INTEGER NOT NULL,
    reason TEXT NOT NULL,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL CHECK(channel IN ('email','sms','admin')),
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    related_type TEXT DEFAULT '',
    related_id INTEGER DEFAULT 0,
    provider TEXT DEFAULT '',
    provider_reference TEXT DEFAULT '',
    provider_response TEXT DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    sent_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    actor_email TEXT DEFAULT '',
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    before_json TEXT DEFAULT '',
    after_json TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

-- v3 operating-system extensions: catalog verification, photo workflow, payments, receipts, launch planning, SEO, staff permissions, ingredients, suppliers, and POS imports.
CREATE TABLE IF NOT EXISTS catalog_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('unverified','owner_verified','needs_price_check','needs_photo','retired')) DEFAULT 'unverified',
    verified_by TEXT DEFAULT '',
    source_name TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    source_notes TEXT DEFAULT '',
    last_verified_at TEXT DEFAULT '',
    next_review_at TEXT DEFAULT '',
    UNIQUE(product_id)
);

CREATE TABLE IF NOT EXISTS product_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    alt_text TEXT NOT NULL,
    image_status TEXT NOT NULL CHECK(image_status IN ('placeholder','needs_reshoot','approved','archived')) DEFAULT 'placeholder',
    source TEXT NOT NULL DEFAULT 'admin_upload',
    is_primary INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 100,
    uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    uploaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_intents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    quote_id INTEGER REFERENCES quote_requests(id) ON DELETE SET NULL,
    provider TEXT NOT NULL DEFAULT 'mock',
    kind TEXT NOT NULL CHECK(kind IN ('deposit','full','balance','manual')) DEFAULT 'deposit',
    amount REAL NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft','requires_payment','paid','failed','canceled','manual_received')) DEFAULT 'requires_payment',
    provider_reference TEXT DEFAULT '',
    checkout_url TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quote_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL REFERENCES quote_requests(id) ON DELETE CASCADE,
    sender_type TEXT NOT NULL CHECK(sender_type IN ('admin','customer','system')) DEFAULT 'system',
    message TEXT NOT NULL,
    amount REAL DEFAULT NULL,
    deposit_required REAL DEFAULT NULL,
    expires_on TEXT DEFAULT '',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS standing_order_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standing_order_id INTEGER NOT NULL REFERENCES standing_orders(id) ON DELETE CASCADE,
    target_date TEXT NOT NULL,
    generated_order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK(status IN ('scheduled','generated','skipped','paused','canceled')) DEFAULT 'scheduled',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS staff_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_key TEXT NOT NULL,
    granted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, permission_key)
);

CREATE TABLE IF NOT EXISTS allergens (
    key TEXT PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_es TEXT NOT NULL,
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS product_allergens (
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    allergen_key TEXT NOT NULL REFERENCES allergens(key) ON DELETE CASCADE,
    cross_contact INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(product_id, allergen_key)
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_es TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT 'lb',
    current_qty REAL NOT NULL DEFAULT 0,
    reorder_point REAL NOT NULL DEFAULT 0,
    cost_per_unit REAL NOT NULL DEFAULT 0,
    supplier_id INTEGER DEFAULT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_ingredients (
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    qty_per_unit REAL NOT NULL DEFAULT 0,
    PRIMARY KEY(product_id, ingredient_id)
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    lead_days INTEGER NOT NULL DEFAULT 1,
    minimum_order TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pos_import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL DEFAULT 'csv',
    filename TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    imported_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'received',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seo_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    meta_description TEXT NOT NULL,
    target_keyword TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft','review','published')) DEFAULT 'draft',
    content_outline TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    block_key TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    body_en TEXT NOT NULL,
    body_es TEXT NOT NULL,
    placement TEXT NOT NULL DEFAULT 'homepage',
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS launch_checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    priority TEXT NOT NULL CHECK(priority IN ('P0','P1','P2','P3')) DEFAULT 'P1',
    owner_role TEXT NOT NULL DEFAULT 'Owner',
    status TEXT NOT NULL CHECK(status IN ('todo','in_progress','blocked','done')) DEFAULT 'todo',
    notes TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS uat_scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT NOT NULL,
    scenario TEXT NOT NULL,
    expected_result TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('untested','pass','fail','needs_change')) DEFAULT 'untested',
    notes TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);


-- v4 customer, growth, costing, and operational hardening extensions.
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    token_suffix TEXT DEFAULT '',
    requester_ip TEXT DEFAULT '',
    status TEXT NOT NULL CHECK(status IN ('requested','used','expired')) DEFAULT 'requested',
    requested_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS customer_favorites (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY(user_id, product_id)
);

CREATE TABLE IF NOT EXISTS order_change_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    request_type TEXT NOT NULL CHECK(request_type IN ('cancel','edit','reschedule','substitution')),
    customer_email TEXT NOT NULL,
    customer_phone TEXT DEFAULT '',
    reason TEXT NOT NULL,
    requested_payload TEXT DEFAULT '{}',
    status TEXT NOT NULL CHECK(status IN ('new','reviewing','approved','declined','completed')) DEFAULT 'new',
    admin_notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    title TEXT DEFAULT '',
    body TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('new','approved','hidden')) DEFAULT 'new',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS local_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'community',
    expected_impact TEXT NOT NULL DEFAULT 'normal',
    demand_multiplier REAL NOT NULL DEFAULT 1.0,
    notes TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weather_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    condition_key TEXT NOT NULL,
    demand_multiplier REAL NOT NULL DEFAULT 1.0,
    categories TEXT DEFAULT 'all',
    prep_notes TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pos_sales_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES pos_import_batches(id) ON DELETE CASCADE,
    customer_name TEXT DEFAULT '',
    customer_email TEXT DEFAULT '',
    customer_phone TEXT DEFAULT '',
    pickup_date TEXT DEFAULT '',
    pickup_time TEXT DEFAULT '',
    product_slug TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    unit_price REAL NOT NULL DEFAULT 0,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_code TEXT UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    business_name TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    subtotal REAL NOT NULL DEFAULT 0,
    discount REAL NOT NULL DEFAULT 0,
    tax REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    balance_due REAL NOT NULL DEFAULT 0,
    terms TEXT NOT NULL DEFAULT 'Due on pickup',
    status TEXT NOT NULL CHECK(status IN ('draft','sent','paid','void')) DEFAULT 'draft',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS loyalty_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    points INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS delivery_zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    min_order REAL NOT NULL DEFAULT 0,
    fee REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('disabled','quote_only','available')) DEFAULT 'quote_only',
    notes TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_key TEXT UNIQUE NOT NULL,
    channel TEXT NOT NULL CHECK(channel IN ('email','sms','admin')),
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_label_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label_date TEXT NOT NULL,
    label_type TEXT NOT NULL DEFAULT 'pickup_bags',
    order_count INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);


-- v5 production integration, security, QA, backup, monitoring, and recipe verification extensions.
CREATE TABLE IF NOT EXISTS two_factor_auth (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    secret_base32 TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 0,
    recovery_codes_json TEXT NOT NULL DEFAULT '[]',
    last_used_step INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    confirmed_at TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS two_factor_challenges (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    verified_at TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS permission_catalog (
    permission_key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS staff_roles (
    role_key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS staff_role_permissions (
    role_key TEXT NOT NULL REFERENCES staff_roles(role_key) ON DELETE CASCADE,
    permission_key TEXT NOT NULL REFERENCES permission_catalog(permission_key) ON DELETE CASCADE,
    PRIMARY KEY(role_key, permission_key)
);

CREATE TABLE IF NOT EXISTS user_staff_roles (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_key TEXT NOT NULL REFERENCES staff_roles(role_key) ON DELETE CASCADE,
    assigned_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(user_id, role_key)
);

CREATE TABLE IF NOT EXISTS supplier_price_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    ingredient_id INTEGER REFERENCES ingredients(id) ON DELETE SET NULL,
    quoted_unit TEXT NOT NULL DEFAULT '',
    quoted_qty REAL NOT NULL DEFAULT 0,
    quoted_total REAL NOT NULL DEFAULT 0,
    effective_on TEXT NOT NULL,
    source_doc TEXT DEFAULT '',
    verified_by TEXT DEFAULT '',
    status TEXT NOT NULL CHECK(status IN ('draft','owner_verified','expired','rejected')) DEFAULT 'draft',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recipe_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    recipe_version TEXT NOT NULL DEFAULT 'v1',
    yield_qty REAL NOT NULL DEFAULT 1,
    yield_unit TEXT NOT NULL DEFAULT 'each',
    labor_minutes REAL NOT NULL DEFAULT 0,
    owner_verified INTEGER NOT NULL DEFAULT 0,
    verified_by TEXT DEFAULT '',
    verified_at TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    updated_at TEXT NOT NULL,
    UNIQUE(product_id, recipe_version)
);

CREATE TABLE IF NOT EXISTS photo_shot_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    shot_type TEXT NOT NULL DEFAULT 'primary product photo',
    priority TEXT NOT NULL CHECK(priority IN ('P0','P1','P2','P3')) DEFAULT 'P1',
    status TEXT NOT NULL CHECK(status IN ('needed','scheduled','shot','approved','reshoot')) DEFAULT 'needed',
    instructions TEXT NOT NULL,
    due_on TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_audit_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_type TEXT NOT NULL CHECK(audit_type IN ('accessibility','mobile','security','performance')),
    tool_name TEXT NOT NULL,
    target_url TEXT NOT NULL,
    score REAL DEFAULT NULL,
    status TEXT NOT NULL CHECK(status IN ('planned','running','pass','fail','needs_manual_review')) DEFAULT 'planned',
    summary TEXT DEFAULT '',
    report_path TEXT DEFAULT '',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_audit_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER REFERENCES qa_audit_runs(id) ON DELETE CASCADE,
    audit_type TEXT NOT NULL,
    check_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('todo','pass','fail','manual','not_applicable')) DEFAULT 'todo',
    severity TEXT NOT NULL CHECK(severity IN ('low','medium','high','critical')) DEFAULT 'medium',
    notes TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backup_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_type TEXT NOT NULL CHECK(backup_type IN ('sqlite','postgres','files')) DEFAULT 'sqlite',
    status TEXT NOT NULL CHECK(status IN ('started','success','failed')) DEFAULT 'started',
    file_path TEXT DEFAULT '',
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    checksum_sha256 TEXT DEFAULT '',
    started_at TEXT NOT NULL,
    finished_at TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS monitoring_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('info','warning','error','critical')) DEFAULT 'info',
    status TEXT NOT NULL CHECK(status IN ('open','acknowledged','resolved')) DEFAULT 'open',
    message TEXT NOT NULL,
    payload_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    resolved_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS integration_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    event_type TEXT NOT NULL,
    related_type TEXT DEFAULT '',
    related_id INTEGER DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('received','processed','ignored','failed')) DEFAULT 'received',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);


-- v6 stabilization and customer-experience extensions.
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_receipt_token ON orders(receipt_token) WHERE receipt_token != '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_quote_public_token ON quote_requests(quote_public_token) WHERE quote_public_token != '';

CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_token TEXT DEFAULT '',
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    event_name TEXT NOT NULL,
    event_payload_json TEXT DEFAULT '{}',
    page_path TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    language_preference TEXT NOT NULL DEFAULT 'en',
    preferred_channel TEXT NOT NULL DEFAULT 'sms',
    do_not_text INTEGER NOT NULL DEFAULT 0,
    do_not_email INTEGER NOT NULL DEFAULT 0,
    substitution_preference TEXT NOT NULL DEFAULT 'call_me',
    saved_pickup_name TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_saved_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_date TEXT NOT NULL,
    notes TEXT DEFAULT '',
    reminder_days_before INTEGER NOT NULL DEFAULT 14,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    batch_date TEXT NOT NULL,
    batch_label TEXT NOT NULL,
    expected_ready_at TEXT NOT NULL,
    produced_qty INTEGER NOT NULL DEFAULT 0,
    reserved_qty INTEGER NOT NULL DEFAULT 0,
    sold_qty INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('planned','mixing','baking','cooling','ready','sold_out','canceled')) DEFAULT 'planned',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    quote_id INTEGER REFERENCES quote_requests(id) ON DELETE SET NULL,
    assigned_role TEXT NOT NULL DEFAULT 'baker',
    assigned_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    task_type TEXT NOT NULL,
    title TEXT NOT NULL,
    due_at TEXT DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL CHECK(status IN ('todo','doing','blocked','done','canceled')) DEFAULT 'todo',
    public_notes TEXT DEFAULT '',
    internal_notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production_task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES production_tasks(id) ON DELETE CASCADE,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    old_status TEXT DEFAULT '',
    new_status TEXT NOT NULL,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seasonal_campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    title_en TEXT NOT NULL,
    title_es TEXT NOT NULL,
    season_start TEXT NOT NULL,
    season_end TEXT NOT NULL,
    preorder_cutoff TEXT NOT NULL,
    pickup_window_notes TEXT DEFAULT '',
    max_orders INTEGER NOT NULL DEFAULT 0,
    current_reserved INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('draft','active','paused','sold_out','closed')) DEFAULT 'draft',
    story_en TEXT DEFAULT '',
    story_es TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seasonal_pickup_windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES seasonal_campaigns(id) ON DELETE CASCADE,
    pickup_date TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 20,
    reserved INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('open','full','closed')) DEFAULT 'open',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    preferred_channel TEXT NOT NULL DEFAULT 'sms',
    language_preference TEXT NOT NULL DEFAULT 'en',
    do_not_text INTEGER NOT NULL DEFAULT 0,
    do_not_email INTEGER NOT NULL DEFAULT 0,
    source TEXT DEFAULT '',
    updated_at TEXT NOT NULL,
    UNIQUE(email, phone)
);

CREATE TABLE IF NOT EXISTS notification_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_id INTEGER NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    provider TEXT DEFAULT '',
    provider_reference TEXT DEFAULT '',
    response TEXT DEFAULT '',
    attempted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_refunds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_intent_id INTEGER REFERENCES payment_intents(id) ON DELETE SET NULL,
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    amount REAL NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('requested','manual_recorded','provider_submitted','succeeded','failed')) DEFAULT 'requested',
    provider_reference TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cash_drawer_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT NOT NULL,
    opened_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    closed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    starting_cash REAL NOT NULL DEFAULT 0,
    expected_cash REAL NOT NULL DEFAULT 0,
    counted_cash REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('open','closed','reconciled')) DEFAULT 'open',
    notes TEXT DEFAULT '',
    opened_at TEXT NOT NULL,
    closed_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tax_export_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    gross_sales REAL NOT NULL DEFAULT 0,
    discounts REAL NOT NULL DEFAULT 0,
    taxable_sales REAL NOT NULL DEFAULT 0,
    tax_collected REAL NOT NULL DEFAULT 0,
    order_count INTEGER NOT NULL DEFAULT 0,
    csv_path TEXT DEFAULT '',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wholesale_blackout_dates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blackout_date TEXT NOT NULL,
    reason TEXT NOT NULL,
    applies_to TEXT NOT NULL DEFAULT 'all',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS partner_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
    approval_type TEXT NOT NULL DEFAULT 'public_showcase',
    approved_by_name TEXT NOT NULL,
    approved_by_email TEXT DEFAULT '',
    approval_date TEXT NOT NULL,
    approved_copy TEXT DEFAULT '',
    rights_notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
