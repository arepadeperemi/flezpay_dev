from api import models

def process_store_waybill(invoice):
    """
    Generate a waybill for a store invoice if it's managed by the system.
    This safely prevents duplicates by checking if a tracking number already exists.
    """
    if invoice.delivery_type != 'system':
        return False, "Not a system-managed delivery"
        
    if invoice.tracking_number:
        return True, "Waybill already generated"
        
    user = invoice.user_id
    business = models.BusinessDetails.objects.filter(user=user).first()
    
    if not business:
        return False, "Business details not found"
        
    country = user.details.first().user_country
    if country == 'NG':
        from api.external.kxpress_api import KxpressAPI
        client = KxpressAPI()
    else:
        from api.external.custom_logistics_api import CustomLogisticsAPI
        client = CustomLogisticsAPI()
        
    try:
        total_weight = 0.0
        items_payload = []
        for invoice_item in invoice.invoice_items.all():
            if invoice_item.item_id not in ['TAX_001', 'DELIVERY_001']:
                item_obj = models.UserItems.objects.filter(user=user, item_id=invoice_item.item_id).first()
                weight = getattr(item_obj, 'item_weight', 0) if item_obj else 0
                total_weight += float(weight or 0) * invoice_item.item_quantity
                
                items_payload.append({
                    "name": invoice_item.item_name,
                    "qty_ordered": str(invoice_item.item_quantity),
                    "price": str(invoice_item.item_amount)
                })

        payload = {
            "creator": {"location_id": "47"},
            "location_id": "47",
            "shipper": {
                "firstname": business.store_pickup_name or business.store_name or "Store",
                "lastname": "Owner",
                "state": str(business.store_pickup_state),
                "city": "",
                "lga": str(business.store_pickup_lga),
                "street": business.store_pickup_address or "",
                "telephone": business.store_pickup_phone or user.details.first().phone or "",
                "email": business.store_pickup_email or user.email,
                "shop_name": business.store_pickup_name or business.store_name or ""
            },
            "receiver": {
                "firstname": invoice.customer_name.split(' ')[0] if invoice.customer_name else "",
                "lastname": invoice.customer_name.split(' ')[-1] if invoice.customer_name and len(invoice.customer_name.split(' ')) > 1 else "",
                "lga": str(invoice.delivery_lga) if invoice.delivery_lga else "",
                "street": invoice.delivery_address or invoice.billing_address or "",
                "city": "",
                "telephone": invoice.customer_phone or "",
                "state": str(invoice.delivery_state) if invoice.delivery_state else "",
                "email": invoice.customer_email or "",
                "name": invoice.customer_name or ""
            },
            "packages": [{
                "package_weight": str(max(1.0, float(total_weight))),
                "package_number": f"PKG-{invoice.invoice_id}",
                "items": items_payload
            }],
            "items": items_payload,
            "pieces": "1",
            "weight": str(max(1.0, float(total_weight)))
        }
        
        waybill_response = None
        api_error = None
        
        try:
            waybill_response = client.generate_waybill(payload)
            if waybill_response.get('status') and 'data' in waybill_response:
                waybill_no = waybill_response['data'].get('waybill_no')
                invoice.tracking_number = waybill_no
                invoice.save(update_fields=['tracking_number'])
                
                # Mark any failed waybill records as resolved
                from django.utils.timezone import now
                models.FailedWaybills.objects.filter(invoice=invoice, is_resolved=False).update(
                    is_resolved=True,
                    resolved_at=now()
                )
            else:
                api_error = waybill_response.get('message', str(waybill_response))
                models.FailedWaybills.objects.update_or_create(
                    invoice=invoice,
                    is_resolved=False,
                    defaults={'error_message': api_error}
                )
        except Exception as e:
            print("Error generating waybill:", e)
            api_error = str(e)
            models.FailedWaybills.objects.update_or_create(
                invoice=invoice,
                is_resolved=False,
                defaults={'error_message': api_error}
            )
            
        try:
            from django.core.mail import send_mail
            from django.template.loader import render_to_string
            import json
            settings_obj = models.SiteSettings.objects.first()
            admin_email = settings_obj.email if settings_obj else 'help@flezpay.com'
            msg = json.dumps(waybill_response, indent=2) if waybill_response else api_error
            html_content = render_to_string('emails/kxpress_api_alert.html', {
                'invoice_id': invoice.invoice_id,
                'api_message': msg
            })
            send_mail(
                subject=f'Logistics Waybill Alert: {invoice.invoice_id}',
                message=f"API Response/Error for invoice {invoice.invoice_id}:\n\n{msg}",
                from_email='no-reply@flezpay.com',
                recipient_list=[admin_email],
                html_message=html_content,
                fail_silently=True,
            )
        except Exception as e_mail:
            print("Error sending waybill email:", e_mail)
            
        return True, "Waybill processed"
    except Exception as e:
        print("Error building waybill payload:", e)
        return False, str(e)
