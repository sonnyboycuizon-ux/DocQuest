from django.utils import timezone
from .models import DocumentRequest

DAILY_REQUEST_LIMIT = 2


def get_today_range_ph():
    now = timezone.localtime(timezone.now())
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return day_start, day_end


def daily_request_context(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user
    if user.is_staff:
        return {
            'sidebar_daily_count': 0,
            'sidebar_daily_remaining': DAILY_REQUEST_LIMIT,
            'sidebar_daily_limit_reached': False,
            'sidebar_daily_limit_applies': False,
        }

    day_start, day_end = get_today_range_ph()
    count = DocumentRequest.objects.filter(
        user=user,
        date_requested__gte=day_start,
        date_requested__lte=day_end,
    ).count()
    remaining = max(0, DAILY_REQUEST_LIMIT - count)
    reached = count >= DAILY_REQUEST_LIMIT
    return {
        'sidebar_daily_count': count,
        'sidebar_daily_remaining': remaining,
        'sidebar_daily_limit_reached': reached,
        'sidebar_daily_limit_applies': True,
    }
