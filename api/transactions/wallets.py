import traceback
import uuid
import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from api.crypto.stellar import StellarWallet
from api.crypto.circle_usdc import CircleUSDC
from api.crypto.bitcoin import BitcoinWallet
from api.functions import misc

logger = logging.getLogger(__name__)


class CryptoWallet(APIView):

    def get(self, request):
        try:
            from api.models import CryptoAssets
            from api.user_data.serializer import CryptoAssetsSerializer
            assets = CryptoAssets.objects.all().prefetch_related('chains')
            serializer = CryptoAssetsSerializer(assets, many=True, context={'request': request})
            return Response({'status': True, 'data': serializer.data})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            if not misc.enforce_permissions(request, 'manage_finances'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_finances' permission."}, status=status.HTTP_403_FORBIDDEN)

            data = request.data.copy()

            asset = data.get("asset")
            chain = data.get("chain")

            if not asset or not chain:
                raise Exception("Asset and chain are required")

            # Handle Stellar XLM
            if asset == "XLM" and chain == "XLM":
                wallet = StellarWallet()
                public_key = wallet.generate_wallet(user_id, asset=asset, chain=chain)
                data = {'wallet': public_key}
            # Handle Circle USDC
            elif asset == "USDC":
                wallet = CircleUSDC()
                wallet_info = wallet.generate_wallet(user_id, asset=asset, chain=chain)
                data = {
                    'wallet': wallet_info['address'],
                    'wallet_id': wallet_info['wallet_id'],
                    'blockchain': wallet_info['blockchain']
                }
            # Handle Bitcoin BTC
            elif asset == "BTC" and chain == "BTC":
                wallet = BitcoinWallet()
                address = wallet.generate_wallet(user_id, asset=asset, chain=chain)
                data = {
                    'wallet': address,
                    'network': wallet.network
                }
            else:
                raise Exception(f"Unsupported asset/chain combination: {asset}/{chain}")

            return Response({'status': True, 'data': data})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)