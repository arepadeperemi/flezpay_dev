from django.urls import path
from . import admin_views, admin_actions
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    # Template views
    path('', admin_views.admin_login_page, name='admin_index'),
    path('login/', admin_views.admin_login_page, name='admin_login_page'),
    path('dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('users/', admin_views.admin_users_page, name='admin_users_page'),
    path('verifications/', admin_views.admin_verifications_page, name='admin_verifications_page'),
    path('transactions/', admin_views.admin_transactions_page, name='admin_transactions_page'),
    path('analytics/', admin_views.admin_analytics_page, name='admin_analytics_page'),
    path('failed-waybills/', admin_views.admin_failed_waybills_page, name='admin_failed_waybills_page'),
    path('error-logs/', admin_views.admin_error_logs_page, name='admin_error_logs_page'),
    path('settings/', admin_views.admin_settings, name='admin_settings'),
    path('mail/', admin_views.admin_mail_page, name='admin_mail_page'),
    path('push-notifications/', admin_views.admin_push_notifications_page, name='admin_push_notifications_page'),
    path('crypto-wallets/', admin_views.admin_crypto_wallets_page, name='admin_crypto_wallets_page'),
    path('users/<str:user_id>/', admin_views.admin_user_detail_page, name='admin_user_detail_page'),
    path('users/<str:user_id>/business/', admin_views.admin_business_details_page, name='admin_business_details_page'),
    
    # API endpoints
    path('api/login', csrf_exempt(admin_views.admin_login), name='admin_api_login'),
    path('api/logout', csrf_exempt(admin_views.admin_logout), name='admin_api_logout'),
    path('api/dashboard/stats', admin_views.admin_dashboard_stats, name='admin_api_dashboard_stats'),
    path('api/dashboard/recent-transactions', admin_views.admin_recent_transactions, name='admin_api_recent_transactions'),
    path('api/dashboard/notifications', admin_views.admin_notifications, name='admin_api_notifications'),
    path('api/dashboard/notifications/mark-read', admin_views.admin_notifications_mark_read, name='admin_api_notifications_mark_read'),
    path('api/dashboard/pending-verifications-count', admin_views.admin_pending_verifications_count, name='admin_api_pending_verifications_count'),
    path('api/analytics/data', admin_views.admin_analytics_data, name='admin_api_analytics_data'),
    path('api/users/search', admin_views.admin_users_search, name='admin_api_users_search'),
    path('api/users', admin_views.admin_users, name='admin_api_users'),
    path('api/users/delete-batch', csrf_exempt(admin_views.admin_users_delete_batch), name='admin_api_users_delete_batch'),
    path('api/users/<str:user_id>', admin_views.admin_user_detail, name='admin_api_user_detail'),
    path('api/users/<str:user_id>/wallets', admin_views.admin_user_wallets, name='admin_api_user_wallets'),
    path('api/users/<str:user_id>/wallets/<str:wallet_id>', csrf_exempt(admin_views.admin_delete_user_wallet), name='admin_api_delete_user_wallet'),
    path('api/users/<str:user_id>/update', csrf_exempt(admin_views.admin_user_update), name='admin_api_user_update'),
    path('api/users/<str:user_id>/transactions', admin_views.admin_user_transactions, name='admin_api_user_transactions'),
    path('api/users/<str:user_id>/verification', admin_views.admin_user_verification, name='admin_api_user_verification'),
    path('api/transactions', admin_views.admin_transactions, name='admin_api_transactions'),
    path('api/verifications', admin_views.admin_verifications, name='admin_api_verifications'),
    path('api/verifications/<int:verification_id>', admin_views.admin_verification_detail, name='admin_api_verification_detail'),
    path('api/verifications/<int:verification_id>/update', csrf_exempt(admin_views.admin_verification_update), name='admin_api_verification_update'),
    path('api/crypto-assets', admin_views.admin_crypto_assets, name='admin_api_crypto_assets'),
    path('api/crypto-assets/add', csrf_exempt(admin_views.admin_add_crypto_asset), name='admin_api_add_crypto_asset'),
    path('api/crypto-chains/add', csrf_exempt(admin_views.admin_add_crypto_chain), name='admin_api_add_crypto_chain'),
    path('api/crypto-assets/<int:asset_id>/delete', csrf_exempt(admin_views.admin_delete_crypto_asset), name='admin_api_delete_crypto_asset'),
    path('api/crypto-chains/<int:chain_id>/delete', csrf_exempt(admin_views.admin_delete_crypto_chain), name='admin_api_delete_crypto_chain'),
    
    # Pending Withdrawals
    path('pending-withdrawals/', admin_views.admin_pending_withdrawals_page, name='admin_pending_withdrawals_page'),
    path('api/pending-withdrawals', admin_views.admin_api_pending_withdrawals, name='admin_api_pending_withdrawals'),
    path('api/pending-withdrawals/batch-retry', csrf_exempt(admin_views.admin_api_batch_retry_withdrawals), name='admin_api_batch_retry_withdrawals'),
    path('api/pending-withdrawals/<str:trx_id>/retry', csrf_exempt(admin_views.admin_api_retry_withdrawal), name='admin_api_retry_withdrawal'),
    
    # Admin sidebar counters
    path('api/sidebar-counters', admin_views.admin_sidebar_counters, name='admin_api_sidebar_counters'),
    
    # Gemini Errors
    path('api/gemini-errors/<int:error_id>/delete', csrf_exempt(admin_views.admin_delete_gemini_error), name='admin_delete_gemini_error'),
    
    # Failed Waybills
    path('api/failed-waybills', admin_views.admin_api_failed_waybills, name='admin_api_failed_waybills'),
    path('api/failed-waybills/batch-retry', csrf_exempt(admin_views.admin_api_batch_retry_waybills), name='admin_api_batch_retry_waybills'),
    path('api/failed-waybills/<int:failure_id>/retry', csrf_exempt(admin_views.admin_api_retry_waybill), name='admin_api_retry_waybill'),
    
    # Admin user management
    path('api/admins', admin_views.admin_list_admins, name='admin_api_list_admins'),
    path('api/admins/create', csrf_exempt(admin_views.admin_create_admin), name='admin_api_create_admin'),
    path('api/admins/update-password', csrf_exempt(admin_views.admin_update_password), name='admin_api_update_password'),
    path('api/admins/<str:user_id>/update', csrf_exempt(admin_views.admin_update_admin), name='admin_api_update_admin'),
    path('api/admins/<str:user_id>/delete', csrf_exempt(admin_views.admin_delete_admin), name='admin_api_delete_admin'),
    path('api/admins/current', admin_views.admin_get_current_admin, name='admin_api_get_current_admin'),
    path('api/admin/settings', admin_views.admin_settings_api, name='admin_api_settings'),
    
    # Business details endpoints
    path('api/business/<str:user_id>/data', admin_views.admin_business_data, name='admin_api_business_data'),
    path('api/business/<str:user_id>/managers', admin_views.admin_business_managers, name='admin_api_business_managers'),
    path('api/business/<str:user_id>/stocks', admin_views.admin_business_stocks, name='admin_api_business_stocks'),
    path('api/business/<str:user_id>/sales', admin_views.admin_business_sales, name='admin_api_business_sales'),
    path('api/business/<str:user_id>/ai-usage', admin_views.admin_business_ai_usage, name='admin_api_business_ai_usage'),
    
    # Mail and Push Notifications endpoints
    path('api/mail/preview', csrf_exempt(admin_views.admin_mail_preview), name='admin_api_mail_preview'),
    path('api/mail/send', csrf_exempt(admin_views.admin_mail_send), name='admin_api_mail_send'),
    path('api/push-notifications/send', csrf_exempt(admin_views.admin_push_notifications_send), name='admin_api_push_notifications_send'),
    
    # Crypto Wallets endpoints
    path('api/crypto-wallets', admin_views.admin_crypto_wallets, name='admin_api_crypto_wallets'),
    path('api/crypto-wallets/<int:wallet_id>/keys', admin_views.admin_crypto_wallet_keys, name='admin_api_crypto_wallet_keys'),
    path('api/crypto-wallets/<int:wallet_id>/check-balance', csrf_exempt(admin_views.admin_crypto_wallet_check_balance), name='admin_api_crypto_wallet_check_balance'),
    path('api/crypto-wallets/check-all-balances', csrf_exempt(admin_views.admin_crypto_wallets_check_all_balances), name='admin_api_crypto_wallets_check_all_balances'),
    path('api/crypto-wallets/<int:wallet_id>/sweep', csrf_exempt(admin_views.admin_crypto_wallet_sweep), name='admin_api_crypto_wallet_sweep'),
    path('api/crypto-wallets/sweep-all', csrf_exempt(admin_views.admin_crypto_wallets_sweep_all), name='admin_api_crypto_wallets_sweep_all'),
    
    # Sweep Wallet Configuration endpoints
    path('api/sweep-wallets', admin_views.admin_sweep_wallets, name='admin_api_sweep_wallets'),
    path('api/sweep-wallets/create', csrf_exempt(admin_views.admin_sweep_wallet_create), name='admin_api_sweep_wallet_create'),
    path('api/sweep-wallets/<int:sweep_wallet_id>/update', csrf_exempt(admin_views.admin_sweep_wallet_update), name='admin_api_sweep_wallet_update'),
    path('api/sweep-wallets/<int:sweep_wallet_id>/delete', csrf_exempt(admin_views.admin_sweep_wallet_update), name='admin_api_sweep_wallet_delete'),

    # Subscription Plans endpoints
    path('api/plans', admin_views.admin_list_plans, name='admin_api_list_plans'),
    path('api/plans/create', csrf_exempt(admin_views.admin_create_plan), name='admin_api_create_plan'),
    path('api/plans/<int:plan_id>/update', csrf_exempt(admin_views.admin_plan_update), name='admin_api_plan_update'),

    # Countries management
    path('api/countries', admin_actions.admin_countries_view, name='admin_api_countries'),
    path('api/countries/<int:pk>', admin_actions.admin_country_detail, name='admin_api_country_detail'),

    # Stores management
    path('stores/', admin_views.admin_stores_page, name='admin_stores_page'),
    path('allowed-countries/', admin_views.admin_allowed_countries_page, name='admin_allowed_countries_page'),
    path('api/stores', admin_views.admin_stores_api, name='admin_api_stores'),
    path('api/stores/grant-ad-credit', csrf_exempt(admin_views.admin_grant_ad_credit), name='admin_api_grant_ad_credit'),
    
    # Expired Accounts management
    path('expired-accounts/', admin_views.admin_expired_accounts_page, name='admin_expired_accounts_page'),
    path('api/expired-accounts', admin_views.admin_api_expired_accounts, name='admin_api_expired_accounts'),
    path('api/expired-accounts/assign-plan', csrf_exempt(admin_views.admin_api_assign_plan), name='admin_api_assign_plan'),
    
    # Custom Website Content Admin
    path('careers/', admin_views.admin_careers_page, name='admin_careers_page'),
    path('job-applications/', admin_views.admin_job_applications_page, name='admin_job_applications_page'),
    path('team-members/', admin_views.admin_team_members_page, name='admin_team_members_page'),
    path('site-settings/', admin_views.admin_site_settings_page, name='admin_site_settings_page'),
    path('contact-messages/', admin_views.admin_contact_messages_page, name='admin_contact_messages_page'),
    path('help-articles/', admin_views.admin_help_articles_page, name='admin_help_articles_page'),
    path('help-articles/add/', admin_views.admin_help_article_form, name='admin_help_article_add'),
    path('help-articles/edit/<int:article_id>/', admin_views.admin_help_article_form, name='admin_help_article_edit'),
    path('blog-posts/', admin_views.admin_blog_posts_page, name='admin_blog_posts_page'),
    path('blog-posts/add/', admin_views.admin_blog_post_form, name='admin_blog_post_add'),
    path('blog-posts/edit/<int:post_id>/', admin_views.admin_blog_post_form, name='admin_blog_post_edit'),

    # Backers management
    path('backers/', admin_views.admin_backers_page, name='admin_backers_page'),
    path('api/backers', csrf_exempt(admin_views.admin_backers), name='admin_api_backers'),
    path('api/backers/<int:backer_id>', csrf_exempt(admin_views.admin_backer_detail), name='admin_api_backer_detail'),
    
    # POS Orders
    path('pos-orders/', admin_views.admin_pos_orders_page, name='admin_pos_orders_page'),
    path('api/pos-orders', admin_views.admin_api_pos_orders, name='admin_api_pos_orders'),
    path('api/pos-orders/<int:order_id>/update-status', csrf_exempt(admin_views.admin_api_update_pos_order_status), name='admin_api_update_pos_order_status'),

    # Invoices
    path('invoices/', admin_views.admin_invoices_page, name='admin_invoices_page'),
    path('api/invoices', admin_views.admin_api_invoices, name='admin_api_invoices'),
    path('api/invoices/<str:invoice_id>', admin_views.admin_api_invoice_detail, name='admin_api_invoice_detail'),

    path('tickets/', admin_views.admin_tickets_page, name='admin_tickets_page'),
    path('tickets/create/', admin_views.admin_ticket_create_page, name='admin_ticket_create_page'),
    path('tickets/<str:ticket_id>/', admin_views.admin_ticket_details_page, name='admin_ticket_details_page'),
    path('api/tickets', csrf_exempt(admin_views.admin_api_tickets), name='admin_api_tickets'),
    path('api/tickets/<str:ticket_id>', csrf_exempt(admin_views.admin_api_ticket_detail), name='admin_api_ticket_detail'),
    path('api/tickets/<str:ticket_id>/messages', csrf_exempt(admin_views.admin_api_ticket_messages), name='admin_api_ticket_messages'),
    
    # Departments
    path('departments/', admin_views.admin_departments_page, name='admin_departments_page'),
    path('api/departments', csrf_exempt(admin_views.admin_api_departments), name='admin_api_departments'),
    path('api/departments/<int:department_id>', csrf_exempt(admin_views.admin_api_department_detail), name='admin_api_department_detail'),
    path('api/admins/search', admin_views.admin_api_admins_search, name='admin_api_admins_search'),
]

