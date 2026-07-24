from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False)
        recent = Notification.objects.filter(user=request.user)[:5]
        return {
            'notifications': recent,
            'unread_count': unread.count(),
        }
    return {'notifications': [], 'unread_count': 0}