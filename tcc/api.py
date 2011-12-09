from django.core.exceptions import ObjectDoesNotExist
from tcc.models import Comment, SpamReport


def make_tree(comments):
    ''' Makes a python tree-structure with nested lists of objects

    Loops the queryset

    Large threads will consume quite a bit of memory
    '''
    root = []
    levels = []
    for c in comments.order_by('parent_id', 'sort_date'):
        c.replies = []
        level = c.depth
        if c.parent:
            while len(levels) > level:
                levels.pop() # pragma: no cover
            levels.append(c)
            levels[level-1].replies.append(c)
        else:
            root.append(c)
            levels = [c]
    return root


def print_tree(tree): # pragma: no cover
    for n in tree:
        print n.id, n.path, n.limit
        print_tree(n.replies)


def get_comments(content_type_id, object_pk):
    return Comment.objects.select_related(
        'user', 'userprofile').filter(
        content_type__id=content_type_id,
        object_pk=object_pk,
    )


def get_comments_limited(content_type_id, object_pk):
    return Comment.limited.select_related(
        'user', 'userprofile'
        ).filter(
        content_type__id=content_type_id,
        object_pk=object_pk,
    )


def get_comments_as_tree(content_type_id, object_pk):
    return make_tree(get_comments(content_type_id=content_type_id,
                                  object_pk=object_pk,
                                  ))


def get_comments_limited_as_tree(content_type_id, object_pk):
    return make_tree( # pragma: no cover
        get_comments_limited(content_type_id=content_type_id,
                             object_pk=object_pk,
                             ))


def get_comments_removed(content_type_id, object_pk):
    return Comment.removed.select_related('user').filter(
        content_type__id=content_type_id, object_pk=object_pk)


def get_comments_disapproved(content_type_id, object_pk):
    return Comment.disapproved.select_related('user').filter(
        content_type__id=content_type_id, object_pk=object_pk)


def post_comment(content_type_id, object_pk,
                 user_id, comment, ip, parent_id=None):
    if parent_id:
        parent = get_comment(parent_id)
        if (not parent) or (not parent.is_open):
            return
    c = Comment(
        content_type_id=content_type_id, object_pk=object_pk, 
        user_id=user_id, comment=comment, parent_id=parent_id, ip_address=ip)
    c.save()
    return c


def post_reply(parent_id, user_id, comment):
    ''' Shortcut for post_comment if there is a parent_id '''
    parent = get_comment(parent_id)
    if (not parent) or (not parent.is_open) or (not parent.reply_allowed()):
        return
    c = Comment(
        content_type_id=parent.content_type_id, object_pk=parent.object_pk,
        site_id=parent.site_id, user_id=user_id, comment=comment,
        parent_id=parent_id)
    c.save()
    return c


def get_comment(comment_id):
    try:
        return Comment.objects.get(id=comment_id)
    except ObjectDoesNotExist:
        return


def get_comment_thread(comment_id):
    c = get_comment(comment_id)
    if c:
        return c.get_thread()


def get_comment_replies(comment_id):
    return Comment.objects.filter(parent=comment_id)


def get_comment_parents(comment_id):
    c = get_comment(comment_id)
    if c:
        return c.get_parents()


def get_comment_thread_root(comment_id):
    c = get_comment(comment_id)
    if c:
        return c.get_root()


def remove_spam_comment(comment_id, user):
    ''' mark comment as spam and remove if the user has the rights'''
    c = get_comment(comment_id)
    if c:
        if c.can_report_spam(user):
            spam_report, created = SpamReport.objects.get_or_create(
                comment=c,
                user=user,
            )

            if created:
                c.spam_report_count += 1

            if c.can_remove_spam(user):
                c.is_spam = True
                c.is_removed = True

            c.save()

        else:
            return
    return c


def remove_comment(comment_id, user):
    ''' mark comment as removed '''
    c = get_comment(comment_id)
    if c:
        if not c.can_remove(user):
            return
        c.is_removed = True
        c.save()
    return c


def restore_comment(comment_id, user):
    ''' restore remove comment '''
    try:
        c = Comment.unfiltered.get(id=comment_id)
        if not c.can_restore(user):
            return
        c.is_removed = False
        c.save()
        return c
    except Comment.DoesNotExist:
        return


def disapprove_comment(comment_id, user):
    ''' disapprove comment '''
    c = get_comment(comment_id)
    if c:
        if not c.can_disapprove(user):
            return
        c.is_approved = False
        c.save()
    return c


def approve_comment(comment_id, user):
    ''' approve comment '''
    try:
        c = Comment.unfiltered.get(id=comment_id)
        if not c.can_approve(user):
            return
        c.is_approved = True
        c.save()
        return c
    except Comment.DoesNotExist:
        return


def open_comment(comment_id, user):
    ''' Mark comment 'open' (replies welcome) '''
    c = get_comment(comment_id)
    if c:
        if not c.can_open(user):
            return
        c.is_open = True
        c.save()
    return c


def close_comment(comment_id, user):
    ''' Mark a comment as closed (no more replies possible) '''
    c = get_comment(comment_id)
    if c:
        if not c.can_close(user):
            return
        c.is_open = False
        c.save()
    return c


def subscribe(comment_id, user):
    r = get_comment_thread_root(comment_id)
    if r:
        r.unsubscribers.remove(user)
    return r


def unsubscribe(comment_id, user):
    r = get_comment_thread_root(comment_id)
    if r:
        r.unsubscribers.add(user)
    return r


def get_user_comments(user_id,
                      content_type_id=None, object_pk=None, site_id=None):
    ''' Returns all (approved, unremoved) comments by user '''
    extra = {}
    if content_type_id:
        extra['content_type__id'] = content_type_id
    if object_pk:
        extra['object_pk'] = object_pk
    if site_id:
        extra['site__id'] = site_id
    return Comment.objects.filter(user__id=user_id, **extra)

