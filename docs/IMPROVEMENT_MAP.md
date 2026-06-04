# Improvement map from the 100-point critique

This file tracks what v2 changed. Some items are fully implemented, some are scaffolded for local demo, and some remain production work because they require real services, real photos, POS data, or owner decisions.

## Catalog, browsing, and content

1. Expanded catalog from 37 products to 117 seeded products.
2. Split many grouped products into named product records.
3. Added Mexican bakery-specific categories and subcategories.
4. Added photo status so admins know which products still need real photography.
5. Added image URL and alt text fields for future real product photos.
6. Spanish product names lead every product card.
7. Added bilingual storefront copy and product rendering.
8. Added accent-insensitive search.
9. Added alias and visual search terms such as pig bread, pink cookie, watermelon cookie, shell bread, and torta bread.
10. Added variant support for stuffed bread and cake options.
11. Added cake flavor variants.
12. Added cake filling variants.
13. Added custom cake quote workflow.
14. Marked decorated cakes as quote-first.
15. Replaced disabled seasonal quote buttons with quote forms.
16. Added quote fields for seasonal products.
17. Added Rosca de Reyes quote product with size/planning notes.
18. Added three Pan de Muerto styles.
19. Added daily case stock counts.
20. Added inventory deduction on checkout.
21. Added inventory movement logging.
22. Added checkout blocking when quantity exceeds stock.
23. Added lead time enforcement.
24. Added pickup-time validation against business hours.
25. Updated seed hours to the current official footer-style schedule and made hours editable.
26. Added open or closed store status.
27. Added editable hours and settings in admin.
28. Added pickup slot capacity checks.
29. Added made-to-order warnings for customers.
30. Added cake checkout and quote detail fields.

## Wholesale and customer workflows

31. Added business name enforcement for premium checkout.
32. Added wholesale application workflow.
33. Added account statuses for pending premium and premium buyers.
34. Added customer registration.
35. Added wholesale approval queue in admin.
36. Added standing order model.
37. Added standing order UI placeholder and API for premium accounts.
38. Added order history for logged-in customers.
39. Added status tracking in admin.
40. Added cancellation status in admin.
41. Added deposit fields and deposit-needed status.
42. Added configurable deposit rate.
43. Added configurable tax-rate setting.
44. Added customer confirmation notification outbox.
45. Added SMS notification outbox.
46. Added email notification outbox.
47. Added admin notification outbox.
48. Added order production tickets through order item detail and production summary.
49. Added more detailed status list.
50. Added retail, cake, and wholesale classification through categories and customer type.
51. Added scrollable admin tables with broader queue visibility.
52. Added pickup date and time grouping data for future calendar views.
53. Added production summary for upcoming orders.
54. Rebuilt forecasting to use local order history.
55. Added explicit caveat that POS history is needed for trusted forecasting.
56. Left weather integration as future production work.
57. Added configurable event records for seasonal planning.
58. Added admin event creation and editing.
59. Events use configurable dates instead of hardcoded-only logic.
60. Added rough ingredient estimates.
61. Added labor notes to events.
62. Added marketing and prep notes for event lead-up.

## Promotions, admin, and operations

63. Added promotion date validation.
64. Added maximum percent discount validation.
65. Added max redemption and per-customer limits.
66. Added promo redemption tracking.
67. Added category targeting.
68. Added bundle buttons as customer-facing bundle helpers.
69. Added auto-apply promotions.
70. Added product margin estimate field for later margin warnings.
71. Blocked negative product prices.
72. Validated stock, lead time, mode, and price relationships.
73. Checkout blocks quote and inactive order modes.
74. Added admin product creation.
75. Added image URL fields for product photos.
76. Added product variants schema and seed variants.
77. Added inactive product order mode.
78. Added allergen note fields.
79. Added ingredient note fields.
80. Added bilingual name and description management fields.

## Security, data quality, and deployment readiness

81. Removed password prefill from UI.
82. Kept demo credentials only in README and server output for local demo.
83. Admin remains linked for demo, but requires authenticated admin session.
84. Added login rate limiting.
85. Added failed-login attempt tracking.
86. Password reset remains future production work.
87. Two-factor authentication remains future production work.
88. Added HttpOnly and SameSite cookies, with optional Secure flag through `JB_SECURE_COOKIES=1`.
89. Added CSRF token checks for authenticated admin/customer mutations.
90. Replaced raw unexpected errors with generic JSON error response.
91. Added audit log.
92. Added basic role separation: admin, guest, pending premium, premium.
93. Normalized database across products, variants, orders, quotes, promotions, partners, hours, settings, inventory, audit, and notifications.
94. Added `schema.sql` and deterministic seed file.
95. Rebuilds database from schema and seeds rather than relying on a shipped mutable database.
96. Added smoke tests.
97. Added better labels and keyboard-friendly native controls, but full accessibility audit remains future work.
98. Improved responsive layout for storefront and admin, but real device QA remains future work.
99. Added partner consent enforcement and demo labeling.
100. Added runbook notes and explicit production gaps for HTTPS, backups, monitoring, real payments, real SMS/email, POS imports, and hosting.
