from django.db import transaction
from django.db.models import Q, Sum
from api import models
import uuid

def resolve_matching_variant(item_obj, color_name=None, color_hex=None, size=None):
    """
    Robust variant resolver matching by color_hex, color_name, and/or size (case-insensitive).
    """
    if not item_obj or not item_obj.variants.exists():
        return None

    variants_qs = item_obj.variants.all()
    
    # Normalize inputs
    c_hex = color_hex.strip() if isinstance(color_hex, str) and color_hex.strip() and color_hex.strip().lower() not in ('null', 'none') else None
    c_name = color_name.strip() if isinstance(color_name, str) and color_name.strip() and color_name.strip().lower() not in ('null', 'none') else None
    s_val = size.strip() if isinstance(size, str) and size.strip() and size.strip().lower() not in ('null', 'none') else None

    # 1. Match both color (hex or name) and size
    if (c_hex or c_name) and s_val:
        q_color = Q()
        if c_hex:
            q_color |= Q(color_hex__iexact=c_hex)
        if c_name:
            q_color |= Q(color_name__iexact=c_name)
        
        v = variants_qs.filter(q_color & Q(size__iexact=s_val)).first()
        if v:
            return v

    # 2. Match by size if provided (common for custom options like 'Pro Max', 'Night Ripped', 'XL')
    if s_val:
        v = variants_qs.filter(size__iexact=s_val).first()
        if v:
            return v
        # Also check if variant_name matches size (for custom variants)
        v = variants_qs.filter(variant_name__iexact=s_val).first()
        if v:
            return v

    # 3. Match by color if provided
    if c_hex or c_name:
        q_color = Q()
        if c_hex:
            q_color |= Q(color_hex__iexact=c_hex)
        if c_name:
            q_color |= Q(color_name__iexact=c_name)
        
        # If size is not specified, prefer variants with empty or null size
        v = variants_qs.filter(q_color & (Q(size__isnull=True) | Q(size=''))).first()
        if not v:
            v = variants_qs.filter(q_color).first()
        if v:
            return v

    # 4. Fallback: if only 1 variant exists for this item, match it
    if variants_qs.count() == 1:
        return variants_qs.first()

    return None


def deduct_invoice_stock(invoice):
    """
    Safely and atomically decrements product and variant stock for all line items on an invoice.
    Syncs total item quantity on UserItems with variant totals.
    """
    if not invoice:
        return

    with transaction.atomic():
        for line_item in invoice.invoice_items.all():
            # Skip non-product system line items like TAX and DELIVERY
            if str(line_item.item_id).startswith(('TAX_', 'DELIVERY_')):
                continue

            real_id = str(line_item.item_id).split('_')[0]
            item_obj = None
            try:
                # Try UUID query first
                item_uuid = uuid.UUID(real_id)
                item_obj = models.UserItems.objects.filter(user=invoice.user_id, item_id=item_uuid).first()
            except (ValueError, TypeError, AttributeError):
                item_obj = models.UserItems.objects.filter(user=invoice.user_id, item_id=real_id).first()

            if not item_obj:
                continue

            quantity = int(line_item.item_quantity or 1)
            if quantity <= 0:
                continue

            has_variants = item_obj.variants.exists()
            if has_variants:
                variant = resolve_matching_variant(
                    item_obj,
                    color_name=line_item.color_name,
                    color_hex=line_item.color_hex,
                    size=line_item.size
                )
                if variant:
                    variant.quantity = max(0, variant.quantity - quantity)
                    variant.save(update_fields=['quantity'])

                # Synchronize parent item stock with sum of variant stock
                total_qty = item_obj.variants.aggregate(total=Sum('quantity'))['total'] or 0
                item_obj.item_quantity = total_qty
                item_obj.save(update_fields=['item_quantity'])
            else:
                item_obj.item_quantity = max(0, (item_obj.item_quantity or 0) - quantity)
                item_obj.save(update_fields=['item_quantity'])
