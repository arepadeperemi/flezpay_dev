from django.conf.urls.static import static

from django.contrib.sitemaps.views import sitemap
from api.sitemaps import site_sitemaps, store_sitemaps, sitemap_index_view
from django.http import HttpResponse

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from flezpay import settings
from django.views.decorators.csrf import csrf_exempt
from api.views import user_logout, LandingPageView, CareersPageView, JobDetailsView, AboutUsPageView, ContactPageView, submit_contact_form, signup_view, public_blogs_ajax, PricingPageView
from api.user_data import data_views

def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")



urlpatterns = [
    path("", LandingPageView.as_view(), name="landing"),
    path("login", TemplateView.as_view(template_name="views/onboarding/login.html"), name="login"),
    path("login/", TemplateView.as_view(template_name="views/onboarding/login.html"), name="login_alt"),
    path("logout", user_logout, name="logout"),
    path("logout/", user_logout, name="logout_alt"),
    path("signup", signup_view, name="signup"),
    path("signup/", signup_view, name="signup_alt"),
    path("register", signup_view, name="register"),
    path("register/", signup_view, name="register_alt"),
    path("2fa", TemplateView.as_view(template_name="views/onboarding/2fa.html")),
    path("2fa/", TemplateView.as_view(template_name="views/onboarding/2fa.html")),
    path("2fa-setup", TemplateView.as_view(template_name="views/onboarding/2fa-setup.html")),
    path("2fa-setup/", TemplateView.as_view(template_name="views/onboarding/2fa-setup.html")),
    path("forgot-password", TemplateView.as_view(template_name="views/onboarding/forgot-password.html")),
    path("forgot-password/", TemplateView.as_view(template_name="views/onboarding/forgot-password.html")),
    path("reset-password", TemplateView.as_view(template_name="views/onboarding/reset-password.html")),
    path("reset-password/", TemplateView.as_view(template_name="views/onboarding/reset-password.html")),
    
    # Authenticated Dashboard Pages
    path("dashboard", login_required(TemplateView.as_view(template_name="views/dashboard/dashboard.html"))),
    path("dashboard/", login_required(TemplateView.as_view(template_name="views/dashboard/dashboard.html"))),
    path("payroll", login_required(TemplateView.as_view(template_name="views/dashboard/payroll.html"))),
    path("payroll/", login_required(TemplateView.as_view(template_name="views/dashboard/payroll.html"))),
    path("tax-credit", login_required(TemplateView.as_view(template_name="views/dashboard/tax-credit.html"))),
    path("tax-credit/", login_required(TemplateView.as_view(template_name="views/dashboard/tax-credit.html"))),
    path("organization", login_required(TemplateView.as_view(template_name="views/dashboard/organization.html"))),
    path("organization/", login_required(TemplateView.as_view(template_name="views/dashboard/organization.html"))),
    path("staff-details/<int:id>", login_required(TemplateView.as_view(template_name="views/dashboard/staff-details.html"))),
    # path("staff-details/", login_required(TemplateView.as_view(template_name="views/dashboard/staff-details.html"))),
    path("create-employee", login_required(TemplateView.as_view(template_name="views/dashboard/create-employee.html"))),
    path("edit-employee/<int:id>", login_required(TemplateView.as_view(template_name="views/dashboard/edit-employee.html"))),
    # path("edit-employee/", login_required(TemplateView.as_view(template_name="views/dashboard/edit-employee.html"))),
    path("create-employee/", login_required(TemplateView.as_view(template_name="views/dashboard/create-employee.html"))),
    path("add-payroll", login_required(TemplateView.as_view(template_name="views/dashboard/add-payroll.html"))),
    path("add-payroll/", login_required(TemplateView.as_view(template_name="views/dashboard/add-payroll.html"))),
    path("edit-payroll/<int:id>", login_required(TemplateView.as_view(template_name="views/dashboard/add-payroll.html"))),
    path("edit-payroll/<int:id>/", login_required(TemplateView.as_view(template_name="views/dashboard/add-payroll.html"))),
    path("pos", login_required(data_views.pos_page_view)),
    path("pos/", login_required(data_views.pos_page_view)),
    path("wallet", login_required(TemplateView.as_view(template_name="views/dashboard/wallet.html"))),
    path("wallet/", login_required(TemplateView.as_view(template_name="views/dashboard/wallet.html"))),
    path("withdraw", login_required(TemplateView.as_view(template_name="views/dashboard/withdraw.html"))),
    path("withdraw/", login_required(TemplateView.as_view(template_name="views/dashboard/withdraw.html"))),
    path("transactions", login_required(TemplateView.as_view(template_name="views/dashboard/transactions.html"))),
    path("transactions/", login_required(TemplateView.as_view(template_name="views/dashboard/transactions.html"))),
    path("ai-manager", login_required(TemplateView.as_view(template_name="views/dashboard/ai-manager.html"))),
    path("ai-manager/", login_required(TemplateView.as_view(template_name="views/dashboard/ai-manager.html"))),
    path("profile", login_required(TemplateView.as_view(template_name="views/dashboard/profile.html"))),
    path("profile/", login_required(TemplateView.as_view(template_name="views/dashboard/profile.html"))),
    path("settings", login_required(TemplateView.as_view(template_name="views/dashboard/settings.html"))),
    path("settings/", login_required(TemplateView.as_view(template_name="views/dashboard/settings.html"))),
    path("verification", login_required(TemplateView.as_view(template_name="views/dashboard/verification.html"))),
    path("verification/", login_required(TemplateView.as_view(template_name="views/dashboard/verification.html"))),
    path("store", data_views.store_view),
    path("store/", data_views.store_view),
    path("store-settings", data_views.store_settings_view),
    path("store-settings/", data_views.store_settings_view),
    path("store-blog", data_views.store_blog_articles_list_view, name="store_blog_articles_list"),
    path("store-blog/", data_views.store_blog_articles_list_view),
    path("store-blog/articles", data_views.store_blog_articles_list_view),
    path("store-blog/articles/", data_views.store_blog_articles_list_view),
    path("store-blog/create", data_views.store_blog_editor_view, name="store_blog_create"),
    path("store-blog/create/", data_views.store_blog_editor_view),
    path("store-blog/edit/<int:post_id>", data_views.store_blog_editor_view, name="store_blog_edit"),
    path("store-blog/edit/<int:post_id>/", data_views.store_blog_editor_view),
    path("domain-management", data_views.domain_management_view),
    path("domain-management/", data_views.domain_management_view),
    path("store-layouts", data_views.store_layouts_page_view),
    path("store-layouts/", data_views.store_layouts_page_view),
    path("store-layouts/builder", data_views.store_builder_view, name="store_builder"),
    path("store-layouts/builder/", data_views.store_builder_view),
    path("online-orders", login_required(TemplateView.as_view(template_name="views/dashboard/online-orders.html")), name="online_orders"),
    path("online-orders/", login_required(TemplateView.as_view(template_name="views/dashboard/online-orders.html"))),
    path("online-orders/<str:order_id>", login_required(TemplateView.as_view(template_name="views/dashboard/online-order-details.html"))),
    path("products", login_required(TemplateView.as_view(template_name="views/dashboard/products.html"))),
    path("products/", login_required(TemplateView.as_view(template_name="views/dashboard/products.html"))),
    path("add-product", login_required(TemplateView.as_view(template_name="views/dashboard/add-product.html"))),
    path("add-product/", login_required(TemplateView.as_view(template_name="views/dashboard/add-product.html"))),
    path("import-products", login_required(TemplateView.as_view(template_name="views/dashboard/import-products.html"))),
    path("import-products/", login_required(TemplateView.as_view(template_name="views/dashboard/import-products.html"))),
    path("edit-product", login_required(TemplateView.as_view(template_name="views/dashboard/edit-product.html"))),
    path("edit-product/", login_required(TemplateView.as_view(template_name="views/dashboard/edit-product.html"))),

    path("analytics", login_required(TemplateView.as_view(template_name="views/dashboard/analytics.html"))),
    path("analytics/", login_required(TemplateView.as_view(template_name="views/dashboard/analytics.html"))),
    path("livechat", login_required(TemplateView.as_view(template_name="views/dashboard/livechat.html"))),
    path("livechat/", login_required(TemplateView.as_view(template_name="views/dashboard/livechat.html"))),
    path("invoices", login_required(TemplateView.as_view(template_name="views/dashboard/invoices.html"))),
    path("invoices/", login_required(TemplateView.as_view(template_name="views/dashboard/invoices.html"))),
    path("create-invoice", login_required(TemplateView.as_view(template_name="views/dashboard/create-invoice.html"))),
    path("create-invoice/", login_required(TemplateView.as_view(template_name="views/dashboard/create-invoice.html"))),

    # Growth Module
    path("growth", login_required(TemplateView.as_view(template_name="views/dashboard/growth/overview.html"))),
    path("growth/", login_required(TemplateView.as_view(template_name="views/dashboard/growth/overview.html"))),
    path("growth/promotions", login_required(TemplateView.as_view(template_name="views/dashboard/growth/promotions.html"))),
    path("growth/promotions/", login_required(TemplateView.as_view(template_name="views/dashboard/growth/promotions.html"))),
    path("growth/promotions/create", login_required(TemplateView.as_view(template_name="views/dashboard/growth/create.html"))),
    path("growth/promotions/create/", login_required(TemplateView.as_view(template_name="views/dashboard/growth/create.html"))),
    path("growth/promotions/details/<uuid:id>", login_required(TemplateView.as_view(template_name="views/dashboard/growth/details.html"))),
    path("growth/promotions/edit/<uuid:id>", login_required(TemplateView.as_view(template_name="views/dashboard/growth/edit.html"))),
    path("growth/promotions/edit/<uuid:id>/", login_required(TemplateView.as_view(template_name="views/dashboard/growth/edit.html"))),
    path("growth/reports", login_required(TemplateView.as_view(template_name="views/dashboard/growth/reports.html"))),
    path("growth/reports/", login_required(TemplateView.as_view(template_name="views/dashboard/growth/reports.html"))),
    path("growth/audience", login_required(TemplateView.as_view(template_name="views/dashboard/growth/audience.html"))),
    path("growth/audience/", login_required(TemplateView.as_view(template_name="views/dashboard/growth/audience.html"))),
    path("growth/ai-assistant", login_required(TemplateView.as_view(template_name="views/dashboard/growth/ai-assistant.html"))),
    path("growth/ai-assistant/", login_required(TemplateView.as_view(template_name="views/dashboard/growth/ai-assistant.html"))),
    path("growth/ai-creator", login_required(TemplateView.as_view(template_name="views/dashboard/growth/ai_creator.html"))),
    path("growth/ai-creator/", login_required(TemplateView.as_view(template_name="views/dashboard/growth/ai_creator.html"))),
    path("growth/settings", login_required(TemplateView.as_view(template_name="views/dashboard/growth/settings.html"))),
    path("growth/settings/", login_required(TemplateView.as_view(template_name="views/dashboard/growth/settings.html"))),

    
    path("privacy-policy", TemplateView.as_view(template_name="views/public/privacy-policy.html")),
    path("privacy-policy/", TemplateView.as_view(template_name="views/public/privacy-policy.html")),
    path("terms", TemplateView.as_view(template_name="views/public/terms.html")),
    path("terms/", TemplateView.as_view(template_name="views/public/terms.html")),
    path("public/ai-manager", TemplateView.as_view(template_name="views/public/ai-manager.html")),
    path("public/ai-manager/", TemplateView.as_view(template_name="views/public/ai-manager.html")),
    path("public/features", TemplateView.as_view(template_name="views/public/features.html"), name="features"),
    path("public/features/", TemplateView.as_view(template_name="views/public/features.html"), name="features_alt"),
    path("public/pos-system", TemplateView.as_view(template_name="views/public/pos-system.html")),
    path("public/pos-system/", TemplateView.as_view(template_name="views/public/pos-system.html")),
    path("public/online-store", TemplateView.as_view(template_name="views/public/online-store.html")),
    path("public/online-store/", TemplateView.as_view(template_name="views/public/online-store.html")),
    path("public/payroll", TemplateView.as_view(template_name="views/public/payroll.html")),
    path("public/payroll/", TemplateView.as_view(template_name="views/public/payroll.html")),
    path("public/about-us", AboutUsPageView.as_view(), name='about_us'),
    path("public/about-us/", AboutUsPageView.as_view(), name='about_us_alt'),
    path("public/careers", CareersPageView.as_view(), name='careers'),
    path("public/careers/", CareersPageView.as_view(), name='careers_alt'),
    path("public/careers/<slug:slug>", JobDetailsView.as_view(), name='career_details'),
    path("public/careers/<slug:slug>/", JobDetailsView.as_view(), name='career_details_alt'),
    path("blog", data_views.blog_list_view, name="blog"),
    path("blog/", data_views.blog_list_view, name="blog_alt"),
    path("blog/<slug:slug>", data_views.blog_details_view, name="blog_details"),
    path("blog/<slug:slug>/", data_views.blog_details_view, name="blog_details_alt"),
    path("public/contact", ContactPageView.as_view(), name='contact_page'),
    path("public/contact/", ContactPageView.as_view(), name='contact_page_alt'),
    path("public/cookie-policy", TemplateView.as_view(template_name="views/public/cookie-policy.html")),
    path("public/cookie-policy/", TemplateView.as_view(template_name="views/public/cookie-policy.html")),
    path("pricing", PricingPageView.as_view(), name="pricing"),
    path("pricing/", PricingPageView.as_view()),
    path("public/pricing", PricingPageView.as_view()),
    path("public/pricing/", PricingPageView.as_view()),
    path("public/testimonial", TemplateView.as_view(template_name="views/public/testimonial.html")),
    path("public/testimonial/", TemplateView.as_view(template_name="views/public/testimonial.html")),
    path("public/testimonials", TemplateView.as_view(template_name="views/public/testimonial.html")),
    path("public/testimonials/", TemplateView.as_view(template_name="views/public/testimonial.html")),
    path("public/faq", TemplateView.as_view(template_name="views/public/faq.html")),
    path("public/faq/", TemplateView.as_view(template_name="views/public/faq.html")),
    path("public/cart", TemplateView.as_view(template_name="views/public/cart.html")),
    path("public/cart/", TemplateView.as_view(template_name="views/public/cart.html")),
    path("public/checkout", TemplateView.as_view(template_name="views/public/checkout.html")),
    path("public/checkout/", TemplateView.as_view(template_name="views/public/checkout.html")),
    path("index.html", RedirectView.as_view(url="/", permanent=False)),
    path("index-2.html", RedirectView.as_view(url="/", permanent=False)),

    path(r'', include("api.urls")),
    path("onepager/verification/", TemplateView.as_view(template_name="onepager/index.html")),
    path("help-center", data_views.help_center_view, name="help_center_no_slash"),
    path("help-center/", data_views.help_center_view, name="help_center"),
    path("help-center/<slug:slug>", data_views.help_center_details_view, name="help_center_details"),
    path("help-center/<slug:slug>/", data_views.help_center_details_view, name="help_center_details_alt"),

    path("api/public/contact-submit", csrf_exempt(submit_contact_form), name="api_submit_contact"),
    path("api/public/blogs", public_blogs_ajax, name="api_public_blogs"),

    # sitemap.xml – index listing both child sitemaps
    path('sitemap.xml', sitemap_index_view, name='sitemap_index'),
    # Child sitemaps: public site pages and online stores (all rendered as views)
    path('sitemap-site.xml', sitemap, {'sitemaps': site_sitemaps}, name='sitemap_site'),
    path('sitemap-stores.xml', sitemap, {'sitemaps': store_sitemaps}, name='sitemap_stores'),
    path('robots.txt', robots_txt, name='robots_txt'),

    path("product/info/<str:item_id>", data_views.public_product_info_view, name="public_product_info"),
    path("product/info/<str:item_id>/", data_views.public_product_info_view, name="public_product_info_alt"),
    
    path('admin', RedirectView.as_view(url='/admin/', permanent=True)),
    path('admin/', include('api.admin_urls')),
    
    path("store/review/<uuid:token_id>/", data_views.review_submission_view, name="store_review"),
    
    # Secure digital product download and asset protection
    path('api/digital-products/download/<str:token>', data_views.digital_product_download_view, name='digital_product_download_no_slash'),
    path('api/digital-products/download/<str:token>/', data_views.digital_product_download_view, name='digital_product_download'),
    path('media/docs/user/digital_products/<path:filepath>', data_views.secure_digital_media_guard, name='secure_digital_media_guard'),
    
    path("<slug:slug>", data_views.store_preview_view, name="store_preview"),
    path("<slug:slug>/", data_views.store_preview_view, name="store_preview_alt"),
    path("<slug:slug>/page/<slug:page_slug>", data_views.store_page_view, name="store_page"),
    path("<slug:slug>/page/<slug:page_slug>/", data_views.store_page_view, name="store_page_alt"),
    path("<slug:slug>/blog", data_views.store_blog_list_view, name="store_blog_list"),
    path("<slug:slug>/blog/", data_views.store_blog_list_view, name="store_blog_list_alt"),
    path("<slug:slug>/blog/<slug:post_slug>", data_views.store_blog_detail_view, name="store_blog_detail"),
    path("<slug:slug>/blog/<slug:post_slug>/", data_views.store_blog_detail_view, name="store_blog_detail_alt"),
    path("<slug:slug>/contact-submit", data_views.store_contact_submit, name="store_contact_submit"),
    path("<slug:slug>/item/<str:item_id>", data_views.store_item_preview_view, name="store_item_preview"),
    path("<slug:slug>/item/<str:item_id>/", data_views.store_item_preview_view, name="store_item_preview_alt"),
    path("<slug:slug>/checkout", data_views.store_checkout_view, name="store_checkout"),
    path("<slug:slug>/checkout/", data_views.store_checkout_view, name="store_checkout_alt"),
]

if settings.DEBUG:  # Serve media files only in development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)