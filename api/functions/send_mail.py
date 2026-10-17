from collections.abc import Sequence
from typing import Optional

from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def mailSender(template=str, subject=str, to=Optional[Sequence[str]], context=None, reply_to=None, attachments=None) -> int:
    html_content = render_to_string(f'emails/{template}', context)
    text = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, to, reply_to=reply_to)
    email.attach_alternative(html_content, 'text/html')
    if attachments:
        for attachment in attachments:
            if isinstance(attachment, tuple):
                email.attach(*attachment)
            elif hasattr(attachment, 'read'):
                email.attach(getattr(attachment, 'name', 'attachment'), attachment.read())
    return email.send()

def mailSenderAsync(template=str, subject=str, to=Optional[Sequence[str]], context=None, reply_to=None, attachments=None):
    import threading
    thread = threading.Thread(target=mailSender, args=(template, subject, to, context, reply_to, attachments))
    thread.daemon = True
    thread.start()