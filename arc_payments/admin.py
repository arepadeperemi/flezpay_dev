"""
Django admin for Arc USDC payment models.
"""
from django.contrib import admin
from django.utils.html import format_html

from arc_payments.config import explorer_tx_url
from arc_payments.models import ArcIndexerState, ArcPaymentSession, ArcUSDCTransfer


@admin.register(ArcPaymentSession)
class ArcPaymentSessionAdmin(admin.ModelAdmin):
    list_display = [
        'payment_id', 'status', 'payment_amount', 'received_amount',
        'order_currency', 'deposit_address_short', 'expires_at', 'created_at',
    ]
    list_filter = ['status', 'network', 'token']
    search_fields = ['payment_id', 'deposit_address', 'tx_hash', 'invoice__invoice_id']
    readonly_fields = [
        'payment_id', 'deposit_address', 'derivation_index', 'wallet_identifier',
        'created_at', 'paid_at', 'detected_at', 'tx_hash_link',
        'explorer_link',
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Payment Session', {
            'fields': ('payment_id', 'status', 'invoice', 'store', 'merchant'),
        }),
        ('Amounts', {
            'fields': (
                'order_currency', 'order_amount',
                'payment_currency', 'payment_amount', 'received_amount',
                'exchange_rate', 'rate_timestamp', 'is_overpaid',
            ),
        }),
        ('Blockchain', {
            'fields': (
                'network', 'chain_id', 'token', 'token_contract',
                'deposit_address', 'derivation_index', 'wallet_identifier',
                'tx_hash_link', 'block_number', 'log_index', 'explorer_link',
            ),
        }),
        ('Timestamps', {
            'fields': ('expires_at', 'created_at', 'detected_at', 'paid_at'),
        }),
    )

    def deposit_address_short(self, obj):
        addr = obj.deposit_address
        return f"{addr[:8]}...{addr[-6:]}" if addr else ''
    deposit_address_short.short_description = 'Deposit Address'

    def tx_hash_link(self, obj):
        if obj.tx_hash:
            return format_html(
                '<code>{}</code>', obj.tx_hash
            )
        return '—'
    tx_hash_link.short_description = 'Transaction Hash'

    def explorer_link(self, obj):
        if obj.tx_hash:
            url = explorer_tx_url(obj.tx_hash)
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">View on Arcscan ↗</a>', url
            )
        return '—'
    explorer_link.short_description = 'Block Explorer'


@admin.register(ArcUSDCTransfer)
class ArcUSDCTransferAdmin(admin.ModelAdmin):
    list_display = [
        'tx_hash_short', 'log_index', 'block_number',
        'from_address_short', 'to_address_short', 'amount',
        'payment', 'processed', 'is_late_payment', 'created_at',
    ]
    list_filter = ['processed', 'is_late_payment', 'network']
    search_fields = ['tx_hash', 'from_address', 'to_address', 'payment__payment_id']
    readonly_fields = [
        'chain_id', 'network', 'tx_hash', 'log_index', 'block_number',
        'from_address', 'to_address', 'amount_raw', 'amount',
        'payment', 'processed', 'is_late_payment', 'created_at',
        'explorer_link',
    ]
    ordering = ['-block_number', '-log_index']

    # Immutable — no delete, no add
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def tx_hash_short(self, obj):
        return f"{obj.tx_hash[:14]}..." if obj.tx_hash else ''
    tx_hash_short.short_description = 'Tx Hash'

    def from_address_short(self, obj):
        a = obj.from_address
        return f"{a[:8]}...{a[-6:]}" if a else ''
    from_address_short.short_description = 'From'

    def to_address_short(self, obj):
        a = obj.to_address
        return f"{a[:8]}...{a[-6:]}" if a else ''
    to_address_short.short_description = 'To'

    def explorer_link(self, obj):
        if obj.tx_hash:
            url = explorer_tx_url(obj.tx_hash)
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">View on Arcscan ↗</a>', url
            )
        return '—'
    explorer_link.short_description = 'Block Explorer'


@admin.register(ArcIndexerState)
class ArcIndexerStateAdmin(admin.ModelAdmin):
    list_display = ['network', 'last_processed_block', 'updated_at']
    readonly_fields = ['updated_at']
