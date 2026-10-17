import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from asgiref.sync import sync_to_async

# We need to import models here carefully to avoid circular imports during startup
# We'll use database_sync_to_async to interact with models

class AgentChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Get the user's business ID
        self.business_id = await self.get_business_id(self.user)
        if not self.business_id:
            await self.close()
            return

        self.room_group_name = f'livechat_store_{self.business_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        # Send active visitors
        active_visitors = await self.get_active_visitors()
        for v in active_visitors:
            await self.send(text_data=json.dumps({
                'type': 'visitor_update',
                **v
            }))
            
        # Send active chats
        active_chats = await self.get_active_chats()
        await self.send(text_data=json.dumps({
            'type': 'active_chats',
            'chats': active_chats
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')
        
        if message_type == 'agent_message':
            chat_id = text_data_json.get('chat_id')
            session_id = text_data_json.get('session_id')
            message = text_data_json.get('message')
            attachment = text_data_json.get('attachment')
            attachment_type = text_data_json.get('attachment_type')
            
            # Save the message and get the visitor session_id
            target_session, msg_data = await self.save_agent_message(chat_id, message, session_id, attachment, attachment_type)
            if target_session:
                # Send message to the specific visitor
                await self.channel_layer.group_send(
                    f'visitor_{target_session}',
                    {
                        'type': 'chat_message',
                        'message': msg_data
                    }
                )
        elif message_type == 'close_chat':
            chat_id = text_data_json.get('chat_id')
            await self.close_chat_db(chat_id)
            # Notify everyone in the store group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_closed',
                    'chat_id': chat_id
                }
            )
        elif message_type == 'delete_chat':
            chat_id = text_data_json.get('chat_id')
            await self.delete_chat_db(chat_id)
            # Notify everyone in the store group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_deleted',
                    'chat_id': chat_id
                }
            )
        elif message_type == 'mark_chat_read':
            chat_id = text_data_json.get('chat_id')
            await self.mark_chat_read_db(chat_id)
        elif message_type == 'save_custom_data':
            chat_id = text_data_json.get('chat_id')
            data = text_data_json.get('data')
            if chat_id and data is not None:
                await self.save_custom_data_db(chat_id, data)

    async def chat_message(self, event):
        # Triggered when a visitor sends a message, or when the agent sends one
        await self.send(text_data=json.dumps(event))
        
    async def visitor_update(self, event):
        # Triggered when a visitor connects/disconnects
        await self.send(text_data=json.dumps(event))

    async def chat_closed(self, event):
        await self.send(text_data=json.dumps(event))

    async def chat_deleted(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def get_business_id(self, user):
        from api.models import BusinessDetails
        try:
            # Resolve the business owner for manager/staff users
            owner = user
            if hasattr(user, 'user_type') and user.user_type in ['manager', 'staff']:
                if getattr(user, 'business_owner', None):
                    owner = user.business_owner
                else:
                    # Try to find via UserManagers record
                    from api.models import UserManagers
                    manager_record = UserManagers.objects.filter(
                        manager_email__iexact=user.user_email
                    ).first()
            business = BusinessDetails.objects.filter(user=owner, store_setup=True).first()
            if not business:
                business = BusinessDetails.objects.filter(user=owner).first()
            return business.id if business else None
        except Exception:
            return None

    @database_sync_to_async
    def get_active_chats(self):
        from api.models import LiveChat
        chats = LiveChat.objects.filter(store_id=self.business_id, status='open').prefetch_related('messages', 'visitor')
        result = []
        for chat in chats:
            all_msgs = list(chat.messages.all())
            messages = [{'id': m.id, 'sender_type': m.sender_type, 'message_text': m.message_text, 'attachment': m.attachment.url if m.attachment else None, 'attachment_type': m.attachment_type, 'created_at': m.created_at.isoformat()} for m in all_msgs]
            unread_count = sum(1 for m in all_msgs if m.sender_type == 'visitor' and not m.is_read)
            result.append({
                'id': chat.id,
                'visitor_id': chat.visitor.session_id if chat.visitor else None,
                'visitor_name': chat.visitor.visitor_name if chat.visitor else None,
                'visitor_email': chat.visitor.visitor_email if chat.visitor else None,
                'visitor_phone': chat.visitor.visitor_phone if chat.visitor else None,
                'country_code': chat.visitor.country_code if chat.visitor else None,
                'custom_data': chat.custom_data,
                'unread': unread_count,
                'has_been_read': unread_count == 0,
                'messages': messages
            })
        return result

    @database_sync_to_async
    def get_active_visitors(self):
        from api.models import StoreVisitor
        from datetime import timedelta
        from django.utils import timezone
        visitors = StoreVisitor.objects.filter(
            store_id=self.business_id,
            is_online=True,
            is_preview=False,
            last_active_at__gte=timezone.now() - timedelta(minutes=2)
        )
        return [{
            'session_id': v.session_id,
            'status': 'online',
            'current_url': v.current_url,
            'visitor_name': v.visitor_name,
            'visitor_email': v.visitor_email,
            'visitor_phone': v.visitor_phone,
            'country_code': v.country_code,
            'user_agent': v.user_agent,
            'language': v.language
        } for v in visitors]

    @database_sync_to_async
    def save_agent_message(self, chat_id, message_text, session_id=None, attachment=None, attachment_type=None):
        from api.models import LiveChat, LiveChatMessage, StoreVisitor
        try:
            if chat_id:
                chat = LiveChat.objects.get(id=chat_id, store_id=self.business_id)
            else:
                visitor = StoreVisitor.objects.get(session_id=session_id, store_id=self.business_id)
                chat, _ = LiveChat.objects.get_or_create(visitor=visitor, store_id=self.business_id, defaults={'status': 'open'})
                
            chat.notification_sent = False
            if chat.status == 'closed':
                chat.status = 'open'
                chat.closed_at = None
            chat.save()
                
            if attachment and 'livechat_attachments/' in attachment:
                attachment = attachment.split('livechat_attachments/')[-1]

            msg = LiveChatMessage.objects.create(
                chat=chat,
                sender_type='agent',
                message_text=message_text,
                is_read=False,
                attachment=attachment,
                attachment_type=attachment_type
            )
            return chat.visitor.session_id, {
                'id': msg.id,
                'chat_id': chat.id,
                'sender_type': msg.sender_type,
                'message_text': msg.message_text,
                'attachment': msg.attachment.url if msg.attachment else None,
                'attachment_type': msg.attachment_type,
                'created_at': msg.created_at.isoformat()
            }
        except (LiveChat.DoesNotExist, StoreVisitor.DoesNotExist):
            return None, None
            
    @database_sync_to_async
    def close_chat_db(self, chat_id):
        from api.models import LiveChat
        from django.utils import timezone
        LiveChat.objects.filter(id=chat_id, store_id=self.business_id).update(status='closed', closed_at=timezone.now())

    @database_sync_to_async
    def delete_chat_db(self, chat_id):
        from api.models import LiveChat
        LiveChat.objects.filter(id=chat_id, store_id=self.business_id).delete()

    @database_sync_to_async
    def mark_chat_read_db(self, chat_id):
        from api.models import LiveChatMessage
        LiveChatMessage.objects.filter(
            chat_id=chat_id, 
            chat__store_id=self.business_id,
            sender_type='visitor', 
            is_read=False
        ).update(is_read=True)

    @database_sync_to_async
    def save_custom_data_db(self, chat_id, data):
        from api.models import LiveChat
        chat = LiveChat.objects.filter(id=chat_id, store_id=self.business_id).first()
        if chat:
            if chat.custom_data:
                chat.custom_data += f"\n\n{data}"
            else:
                chat.custom_data = data
            chat.save(update_fields=['custom_data'])

class VisitorChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Expected URL route: ws/livechat/visitor/<business_slug>/<session_id>/
        self.store_slug = self.scope['url_route']['kwargs']['store_slug']
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        
        self.business_id = await self.get_business_by_slug(self.store_slug)
        if not self.business_id:
            await self.close()
            return

        user = self.scope.get('user')
        self.is_store_owner = False
        if user and user.is_authenticated:
            self.is_store_owner = await self.check_is_store_owner(user, self.business_id)

        self.visitor_group_name = f'visitor_{self.session_id}'
        self.store_group_name = f'livechat_store_{self.business_id}'

        # Join personal visitor group (to receive replies from agent)
        await self.channel_layer.group_add(
            self.visitor_group_name,
            self.channel_name
        )

        await self.accept()
        
        # Track active presence
        visitor_data = await self.update_visitor_status(True)
        await self.channel_layer.group_send(
            self.store_group_name,
            {'type': 'visitor_update', **visitor_data}
        )
        
        history = await self.get_visitor_history()
        await self.send(text_data=json.dumps({
            'type': 'chat_history',
            'messages': history
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'visitor_group_name'):
            visitor_data = await self.update_visitor_status(False)
            await self.channel_layer.group_send(
                self.store_group_name,
                {'type': 'visitor_update', **visitor_data}
            )
            await self.channel_layer.group_discard(
                self.visitor_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')

        if message_type == 'ping':
            # Update last_active_at implicitly via save
            await self.update_visitor_status(True)
            
        elif message_type == 'visitor_init':
            name = text_data_json.get('name')
            email = text_data_json.get('email')
            phone = text_data_json.get('phone')
            country = text_data_json.get('country')
            state = text_data_json.get('state')
            current_url = text_data_json.get('current_url')
            visitor_data = await self.update_visitor_details(name, email, phone, country, state, current_url)
            await self.channel_layer.group_send(
                self.store_group_name,
                {'type': 'visitor_update', **visitor_data}
            )
            
        elif message_type == 'visitor_message':
            message = text_data_json.get('message')
            current_url = text_data_json.get('current_url', '')
            attachment = text_data_json.get('attachment', None)
            attachment_type = text_data_json.get('attachment_type', None)
            
            chat_id, msg_data = await self.save_visitor_message(message, current_url, attachment, attachment_type)
            if chat_id:
                # Send message to the agent group
                await self.channel_layer.group_send(
                    self.store_group_name,
                    {
                        'type': 'chat_message',
                        'message': msg_data
                    }
                )
                
        elif message_type == 'mark_as_read':
            await self.mark_agent_messages_read_db()
                
        elif message_type == 'close_chat':
            chat_id = await self.close_active_chat_for_visitor()
            if chat_id:
                await self.channel_layer.group_send(
                    self.store_group_name,
                    {
                        'type': 'chat_closed',
                        'chat_id': chat_id
                    }
                )

    async def chat_message(self, event):
        # Triggered when agent replies
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def mark_agent_messages_read_db(self):
        from api.models import LiveChat
        chats = LiveChat.objects.filter(
            visitor__session_id=self.session_id,
            store_id=self.business_id
        ).order_by('-created_at')
        if chats.exists():
            chat = chats.first()
            chat.messages.filter(sender_type='agent', is_read=False).update(is_read=True)
            if chat.notification_sent:
                chat.notification_sent = False
                chat.save(update_fields=['notification_sent'])

    @database_sync_to_async
    def get_business_by_slug(self, slug):
        from api.models import BusinessDetails
        try:
            business = BusinessDetails.objects.filter(store_slug=slug).first()
            return business.id if business else None
        except Exception:
            return None

    @database_sync_to_async
    def check_is_store_owner(self, user, business_id):
        from api.models import BusinessDetails
        business = BusinessDetails.objects.filter(id=business_id).first()
        if not business:
            return False
        if business.user == user:
            return True
        if hasattr(user, 'user_type') and user.user_type in ['manager', 'staff'] and getattr(user, 'business_owner', None) == business.user:
            return True
        return False

    @database_sync_to_async
    def update_visitor_status(self, is_active):
        from api.models import StoreVisitor
        is_preview = getattr(self, 'is_store_owner', False)
        visitor, _ = StoreVisitor.objects.get_or_create(
            session_id=self.session_id,
            store_id=self.business_id,
            defaults={'last_active_at': timezone.now(), 'is_preview': is_preview}
        )
        visitor.is_preview = is_preview
        visitor.is_online = is_active
        visitor.last_active_at = timezone.now()
        
        headers_dict = dict(self.scope.get('headers', []))
        if b'user-agent' in headers_dict:
            visitor.user_agent = headers_dict[b'user-agent'].decode('utf-8')
        if b'accept-language' in headers_dict:
            visitor.language = headers_dict[b'accept-language'].decode('utf-8').split(',')[0]
            
        visitor.save()
            
        return {
            'session_id': self.session_id,
            'status': 'online' if is_active else 'offline',
            'current_url': visitor.current_url,
            'visitor_name': visitor.visitor_name,
            'visitor_email': visitor.visitor_email,
            'visitor_phone': visitor.visitor_phone,
            'country_code': visitor.country_code,
            'user_agent': visitor.user_agent,
            'language': visitor.language
        }
        
    @database_sync_to_async
    def close_active_chat_for_visitor(self):
        from api.models import LiveChat
        chat = LiveChat.objects.filter(visitor__session_id=self.session_id, store_id=self.business_id).first()
        if chat:
            chat_id = chat.id
            chat.delete()
            return chat_id
        return None
        
    @database_sync_to_async
    def update_visitor_details(self, name, email, phone, country, state, current_url):
        from api.models import StoreVisitor
        is_preview = getattr(self, 'is_store_owner', False)
        visitor, _ = StoreVisitor.objects.get_or_create(
            session_id=self.session_id,
            store_id=self.business_id,
            defaults={'is_preview': is_preview}
        )
        visitor.is_preview = is_preview
        if name: visitor.visitor_name = name
        if email: visitor.visitor_email = email
        if phone: visitor.visitor_phone = phone
        if country: visitor.country_code = country
        if state: visitor.state = state
        if current_url: visitor.current_url = current_url
        
        headers_dict = dict(self.scope.get('headers', []))
        if b'user-agent' in headers_dict:
            visitor.user_agent = headers_dict[b'user-agent'].decode('utf-8')
        if b'accept-language' in headers_dict:
            visitor.language = headers_dict[b'accept-language'].decode('utf-8').split(',')[0]
            
        visitor.save()
        return {
            'session_id': self.session_id,
            'status': 'online',
            'current_url': visitor.current_url,
            'visitor_name': visitor.visitor_name,
            'visitor_email': visitor.visitor_email,
            'visitor_phone': visitor.visitor_phone,
            'country_code': visitor.country_code,
            'state': visitor.state,
            'user_agent': visitor.user_agent,
            'language': visitor.language
        }
        
    @database_sync_to_async
    def get_visitor_history(self):
        from api.models import LiveChat
        chats = LiveChat.objects.filter(
            visitor__session_id=self.session_id,
            store_id=self.business_id
        ).order_by('-created_at')
        if not chats.exists():
            return []
            
        chat = chats.first()
        messages = chat.messages.all().order_by('created_at')
        return [
            {
                'id': msg.id,
                'chat_id': chat.id,
                'sender_type': msg.sender_type,
                'message_text': msg.message_text,
                'attachment': msg.attachment.url if msg.attachment else None,
                'attachment_type': msg.attachment_type,
                'created_at': msg.created_at.isoformat(),
            } for msg in messages
        ]
        
    @database_sync_to_async
    def save_visitor_message(self, message_text, current_url, attachment=None, attachment_type=None):
        if attachment and 'livechat_attachments/' in attachment:
            attachment = attachment.split('livechat_attachments/')[-1]
            
        from api.models import LiveChat, LiveChatMessage, StoreVisitor
        is_preview = getattr(self, 'is_store_owner', False)
        visitor, _ = StoreVisitor.objects.get_or_create(
            session_id=self.session_id,
            store_id=self.business_id,
            defaults={'is_preview': is_preview}
        )
        visitor.is_preview = is_preview
        if current_url:
            visitor.current_url = current_url
            visitor.save()
            
        chat, _ = LiveChat.objects.get_or_create(
            visitor=visitor,
            store_id=self.business_id,
            status='open'
        )
        if chat.notification_sent:
            chat.notification_sent = False
            chat.save(update_fields=['notification_sent'])
        
        msg = LiveChatMessage.objects.create(
            chat=chat,
            sender_type='visitor',
            message_text=message_text,
            attachment=attachment,
            attachment_type=attachment_type
        )
        return chat.id, {
            'id': msg.id,
            'chat_id': chat.id,
            'sender_type': msg.sender_type,
            'message_text': msg.message_text,
            'attachment': msg.attachment.url if msg.attachment else None,
            'attachment_type': msg.attachment_type,
            'created_at': msg.created_at.isoformat(),
            'visitor': {
                'session_id': visitor.session_id,
                'current_url': visitor.current_url
            }
        }
