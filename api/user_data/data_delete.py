import traceback
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from api import models
from api.functions import misc
from django.shortcuts import get_object_or_404

from api.models import CashierDepartments, UserItems


class DeleteCartItem(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            cart_item = models.UserCartItems.objects.get(user=instance, id=request.data['id'])
            cart_item.delete()
            return Response({'status': True, 'message': "Data deleted successfully"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error},
                            status=status.HTTP_400_BAD_REQUEST)


class DeleteProducts(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            
            try:
                from api.functions.subscription_validation import SubscriptionManager, SubscriptionLimitError
                SubscriptionManager(instance).require_inventory()
            except SubscriptionLimitError as e:
                return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
                
            product_ids = request.data.get("product_ids", [])
            cart_item = models.UserItems.objects.filter(user=instance, item_id__in=product_ids)
            cart_item.delete()
            return Response({'status': True, 'message': "Data deleted successfully"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            return Response({'status': False, 'message': error},
                            status=status.HTTP_400_BAD_REQUEST)
        


class DeleteDepartment(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            dept_id = request.data.get('id')
            
            if not dept_id:
                return Response({'status': False, 'message': "Department ID is required"}, status=status.HTTP_400_BAD_REQUEST)

            collection = models.CashierDepartments.objects.get(uniq_id=dept_id, user=instance)

            # Check if any products are using this department's NAME
            # item_department is a text field in UserItems
            get_products = models.UserItems.objects.filter(user=instance, item_department=collection.department_name)

            if get_products.exists():
                return Response({
                    'status': False, 
                    'message': f"Cannot delete '{collection.department_name}'. There are {get_products.count()} products currently assigned to this category."
                }, status=status.HTTP_400_BAD_REQUEST)

            collection.delete()
            return Response({'status': True, 'message': "Category deleted successfully"})
        except models.CashierDepartments.DoesNotExist:
            return Response({'status': False, 'message': "Category not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error},
                            status=status.HTTP_400_BAD_REQUEST)

class DeleteCategory(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            cat_id = request.data.get('id')
            
            if not cat_id:
                return Response({'status': False, 'message': "Category ID is required"}, status=status.HTTP_400_BAD_REQUEST)

            collection = models.ProductCategories.objects.get(uniq_id=cat_id, user=instance)

            # Check if any products are using this category's NAME
            # item_category is a text field in UserItems
            get_products = models.UserItems.objects.filter(user=instance, item_category=collection.category_name)

            if get_products.exists():
                return Response({
                    'status': False, 
                    'message': f"Cannot delete '{collection.category_name}'. There are {get_products.count()} products currently assigned to this category."
                }, status=status.HTTP_400_BAD_REQUEST)

            collection.delete()
            return Response({'status': True, 'message': "Category deleted successfully"})
        except models.ProductCategories.DoesNotExist:
            return Response({'status': False, 'message': "Category not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error},
                            status=status.HTTP_400_BAD_REQUEST)


class DeleteUserPayroll(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)  # Must be called first to set request.actual_user_id
            if not misc.enforce_permissions(request, 'manage_payroll'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_payroll' permission."}, status=status.HTTP_403_FORBIDDEN)
            instance = models.UserSecure.objects.get(user_id=user_id)

            if not instance.kyb_verified:
                return Response({'status': False, 'message': "Tier 2 account verification is required to manage employee payroll."}, status=status.HTTP_403_FORBIDDEN)

            payroll_id = request.data.get('id')

            if not payroll_id:
                return Response({'status': False, 'message': 'Payroll ID is required'},
                                status=status.HTTP_400_BAD_REQUEST)

            business_details = models.BusinessDetails.objects.filter(user=instance).first()
            if business_details and business_details.enable_auto_payroll:
                return Response({
                    'status': False,
                    'message': "Cannot delete employee payroll while Auto Payroll is enabled. Please disable Auto Payroll on the dashboard first."
                }, status=status.HTTP_400_BAD_REQUEST)

            payroll = get_object_or_404(models.UserPayroll, user_id=instance, id=payroll_id)
            payroll.delete()

            return Response({'status': True, 'message': 'Payroll deleted successfully'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': False,
                'message': str(e),
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)

class DeleteStaffAccount(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            staff_id = request.data.get('id')

            if not staff_id:
                return Response({'status': False, 'message': 'Staff ID is required'},
                                status=status.HTTP_400_BAD_REQUEST)

            staff_user = get_object_or_404(models.UserSecure, business_owner=instance, uniq_id=staff_id)
            staff_user.delete()

            return Response({'status': True, 'message': 'Staff deleted successfully'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': False,
                'message': str(e),
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)


class DeleteWithdrawalAccount(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            if not misc.enforce_permissions(request, 'manage_finances'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_finances' permission."}, status=status.HTTP_403_FORBIDDEN)
            instance = models.UserSecure.objects.get(user_id=user_id)
            withdrawal_id = request.data.get('id')


            payroll = get_object_or_404(models.UserWithdrawalAccounts, withdrawal_unique=instance, uniq_id=withdrawal_id)
            payroll.delete()

            return Response({'status': True, 'message': 'Payroll deleted successfully'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': False,
                'message': str(e),
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)


class DeleteAccount(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            
            password = request.data.get('password', '')
            pin = request.data.get('pin', '')
            
            if password:
                if not instance.check_password(password):
                    return Response({
                        'status': False,
                        'message': "Invalid password. Account deletion aborted."
                    }, status=status.HTTP_401_UNAUTHORIZED)
            elif pin:
                pin_exists = models.AuthenticationPin.objects.filter(
                    user_pin=pin, 
                    user_phone=instance.user_email, 
                    user_pin_type="delete_account"
                )
                if not pin_exists.exists():
                    return Response({
                        'status': False,
                        'message': "Invalid authorization PIN. Please enter the correct PIN sent to your email.",
                    }, status=status.HTTP_401_UNAUTHORIZED)
                pin_exists.delete()
            else:
                return Response({
                    'status': False,
                    'message': 'Password or Authorization PIN is required to confirm account deletion'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Perform soft delete internally by setting is_active = False
            # Safely preserves historical database records for compliance
            instance.is_active = False
            instance.save()
            
            # Send logout signal if WebSocket channel layer is available
            try:
                from api.signals import send_logout_signal
                send_logout_signal(instance.user_id)
            except Exception:
                pass
            
            return Response({
                'status': True, 
                'message': 'Account deleted successfully.'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            return Response({
                'status': False,
                'message': error,
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)

class DeleteInvoice(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user_instance = models.UserSecure.objects.get(user_id=user_id)
            invoice_id = request.data.get('invoice_id')
            
            if not invoice_id:
                raise Exception("Invoice ID is required")
                
            invoice = models.UserInvoices.objects.get(user_id=user_instance, invoice_id=invoice_id)
            invoice.delete()
            
            return Response({'status': True, 'message': "Invoice deleted successfully"})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)