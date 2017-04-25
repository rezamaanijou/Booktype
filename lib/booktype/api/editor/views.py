import json

from rest_framework import generics, mixins, viewsets, views, status
from rest_framework.response import Response
from rest_framework.decorators import detail_route
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

import sputnik
from django.contrib.auth.models import User
from django_filters.rest_framework import DjangoFilterBackend

from booki.editor.models import Book, Language, Chapter
from booktype.apps.core.models import BookRole, Role
from booki.utils.log import logBookHistory
from booktype.utils.security import BookSecurity

from . import serializers
from .filters import ChapterFilter, BookUserListFilter

from ..views import BooktypeViewSetMixin
from ..security import IsAdminOrBookOwner, BooktypeBookSecurity
from ..core import serializers as core_serializers


class LanguageViewSet(
        mixins.RetrieveModelMixin, mixins.ListModelMixin,
        BooktypeViewSetMixin, viewsets.GenericViewSet
        ):

    """
    API endpoint that allows languages to be viewed or listed.

    retrieve:
    Return a language instance

    list:
    Return all the languages
    """

    required_perms = ['api.manage_languages']
    queryset = Language.objects.all()
    serializer_class = serializers.LanguageSerializer


class BookViewSet(BooktypeViewSetMixin, viewsets.ModelViewSet):

    """
    API endpoint that allows books to be viewed or edited.

    list:
    Return all the books ordered by creation date

    retrieve:
    Return a language instance

    create:
    Allows creating a new book

    partial_update:
    Executes a partial book instance update

    update:
    Executes a full book instance update

    destroy:
    Allows deleting a book from the system
    """

    required_perms = {
        'default': ['api.manage_books'],
        'grant_user': ['core.manage_roles'],
        'grant_user_multi': ['core.manage_roles'],
        'remove_grant_user_multi': ['core.manage_roles'],
    }
    queryset = Book.objects.all().order_by('-created')

    serializer_class = serializers.BookSerializer
    serializer_action_classes = {
        'list': serializers.BookListSerializer,
        'create': serializers.BookCreateSerializer
    }

    filter_backends = (DjangoFilterBackend,)
    filter_fields = ['owner_id', 'language_id']

    @detail_route(url_path='users-by-role', permission_classes=[IsAdminOrBookOwner, BooktypeBookSecurity])
    def users_by_role(self, request, pk=None):
        """
        Returns a list of all roles in the current book with the members assigned
        on each role
        """

        # @TODO: discuss if we should check with book_security module if requesting user has_perms
        # to view the users by role. For now we're just allowing owner and superuser

        # @NOTE we could create a decorator to check some defined permissions and
        # raise a rest_framework.exceptions.PermissionDenied exception from the inside of decorator

        book = self.get_object()
        roles = book.bookrole_set.all()
        serializer = core_serializers.BookRoleSerializer(
            roles, context={'request': request},
            many=True
        )
        return Response(serializer.data)

    @detail_route(
        methods=['post'], url_path='grant-user',
        permission_classes=[IsAdminOrBookOwner, BooktypeBookSecurity])
    def grant_user(self, request, pk=None):
        """
        Grants a given user to be part of certain given role name under the
        current book

        parameters:
            -   name: role_name
                required: true
                type: Unique role name to be granted
            -   name: user_id
                required: true
        """
        book = self.get_object()

        try:
            user = User.objects.get(id=request.data['user_id'])
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            role = Role.objects.get(name=request.data['role_name'])
        except Role.DoesNotExist:
            return Response({'detail': 'Role not found'}, status=status.HTTP_404_NOT_FOUND)

        book_role, _ = BookRole.objects.get_or_create(
            role=role, book=book)
        book_role.members.add(user)

        serializer = core_serializers.BookRoleSerializer(book_role, context={'request': request})
        return Response(serializer.data)

    @detail_route(
        methods=['post'], url_path='grant-user/multi',
        permission_classes=[BooktypeBookSecurity])
    def grant_user_multi(self, request, pk=None):
        """
        Grants a given user to be part of given role names under the
        current book

        parameters:
            -   name: role_names
                required: true
                type: Unique role names array to be granted
            -   name: user_id
                required: true
        """

        role_names = request.data.getlist('role_names[]')

        if not role_names:
            raise ValidationError({'role_names': ['Not valid array']})

        book = self.get_object()

        try:
            user = User.objects.get(id=request.data['user_id'])
        except User.DoesNotExist:
            raise ValidationError({'user_id': ['User not found']})

        response_data = []
        for role_name in role_names:
            try:
                role = Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                raise ValidationError(
                    {'role_names': ['Role with name "{}" not found'.format(role_name)]}
                )

            book_role, _ = BookRole.objects.get_or_create(
                role=role, book=book)
            book_role.members.add(user)

            serializer = core_serializers.BookRoleSerializer(book_role, context={'request': request})
            response_data.append(serializer.data)

        return Response(response_data)

    @detail_route(
        methods=['post'], url_path='remove-grant-user/multi',
        permission_classes=[BooktypeBookSecurity])
    def remove_grant_user_multi(self, request, pk=None):
        """
        Remove given roles from the user
        current book

        parameters:
            -   name: role_names
                required: true
                type: Unique role names array to be granted
            -   name: user_id
                required: true
        """

        role_names = request.data.getlist('role_names[]')

        if not role_names:
            raise ValidationError({'role_names': ['Not valid array']})

        book = self.get_object()

        try:
            user = User.objects.get(id=request.data['user_id'])
        except User.DoesNotExist:
            raise ValidationError({'user_id': ['User not found']})

        response_data = {'removed': []}
        for role_name in role_names:
            try:
                role = Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                raise ValidationError(
                    {'role_names': ['Role with name "{}" not found'.format(role_name)]}
                )

            try:
                book_role = BookRole.objects.get(
                    role=role, book=book)
            except BookRole.DoesNotExist:
                continue

            book_role.members.remove(user)
            response_data['removed'].append(role.name)

        return Response(response_data)


class ChapterListCreate(generics.ListCreateAPIView):
    """
    API endpoint that lists/creates chapters of a specific book.
    """

    model = Chapter
    serializer_class = serializers.ChapterListCreateSerializer
    filter_class = ChapterFilter

    def __init__(self):
        super(ChapterListCreate, self).__init__()
        self._book = None

    def _get_book(self):
        try:
            self._book = Book.objects.get(id=self.kwargs.get('pk', None))
        except Book.DoesNotExist:
            raise NotFound

        return self._book

    def get_queryset(self):
        if self._book:
            return self._book.chapter_set.all()
        return Chapter.objects.all()

    def get(self, request, *args, **kwargs):
        book_security = BookSecurity(request.user, self._get_book())

        if book_security.has_perm('api.manage_books') and book_security.has_perm('api.list_chapters'):
            return super(ChapterListCreate, self).get(request, *args, **kwargs)

        raise PermissionDenied

    def post(self, request, *args, **kwargs):
        book_security = BookSecurity(request.user, self._get_book())

        if book_security.has_perm('api.manage_books') and book_security.has_perm('api.create_chapters'):
            return super(ChapterListCreate, self).post(request, *args, **kwargs)

        raise PermissionDenied


class ChapterRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint that retieve/update/delete chapter.
    """

    model = Chapter
    serializer_class = serializers.ChapterRetrieveUpdateDestroySerializer
    filter_class = ChapterFilter

    def __init__(self):
        super(ChapterRetrieveUpdateDestroy, self).__init__()
        self._book = None
        self._chapter = None

    def _get_book(self):
        try:
            self._book = Book.objects.get(id=self.kwargs.get('book_id', None))
        except Book.DoesNotExist:
            raise NotFound

        return self._book

    def _delete_notifications(self):
        # TODO
        # this is just playground
        # we must create separate tool to push messages through the sputnik channel from API endpoints
        # without having clientID in request

        # message_info
        channel_name = "/chat/{}/".format(self._book.id)
        clnts = sputnik.smembers("sputnik:channel:{}:channel".format(channel_name))
        message = {
            'channel': channel_name,
            "command": "message_info",
            "from": self.request.user.username,
            "email": self.request.user.email,
            "message_id": "user_delete_chapter",
            "message_args": [self.request.user.username, self._chapter.title]
        }

        for c in clnts:
            if c.strip() != '':
                sputnik.push("ses:%s:messages" % c, json.dumps(message))

        # chapter delete
        channel_name = "/booktype/book/{}/{}/".format(self._book.id, self._book.version.get_version())
        clnts = sputnik.smembers("sputnik:channel:{}:channel".format(channel_name))
        message = {
            'channel': channel_name,
            "command": "chapter_delete",
            "chapterID": self._chapter.id
        }

        for c in clnts:
            if c.strip() != '':
                sputnik.push("ses:%s:messages" % c, json.dumps(message))

        # notificatoin message
        message = {
            'channel': channel_name,
            'command': 'notification',
            'message': 'notification_chapter_was_deleted',
            'username': self.request.user.username,
            'message_args': (self._chapter.title,)
        }

        for c in clnts:
            if c.strip() != '':
                sputnik.push("ses:%s:messages" % c, json.dumps(message))


    def get_queryset(self):
        return self._book.chapter_set.all()

    def get(self, request, *args, **kwargs):
        book_security = BookSecurity(request.user, self._get_book())

        if book_security.has_perm('api.manage_books') and book_security.has_perm('api.list_chapters'):
            return super(ChapterRetrieveUpdateDestroy, self).get(request, *args, **kwargs)

        raise PermissionDenied

    def put(self, request, *args, **kwargs):
        book_security = BookSecurity(request.user, self._get_book())

        if book_security.has_perm('api.manage_books') and book_security.has_perm('api.update_chapters'):
            return super(ChapterRetrieveUpdateDestroy, self).put(request, *args, **kwargs)

        raise PermissionDenied

    def patch(self, request, *args, **kwargs):
        book_security = BookSecurity(request.user, self._get_book())

        if book_security.has_perm('api.manage_books') and book_security.has_perm('api.update_chapters'):
            return super(ChapterRetrieveUpdateDestroy, self).patch(request, *args, **kwargs)

        raise PermissionDenied

    def delete(self, request, *args, **kwargs):
        book_security = BookSecurity(request.user, self._get_book())

        if book_security.has_perm('api.manage_books') and book_security.has_perm('api.delete_chapters'):
            self._chapter = self.get_object()

            respone = super(ChapterRetrieveUpdateDestroy, self).delete(request, *args, **kwargs)

            if respone.status_code is status.HTTP_204_NO_CONTENT:
                self._delete_notifications()

                logBookHistory(book=self._book, version=self._book.version,
                               args={'chapter': self._chapter.title},
                               user=self.request.user, kind='chapter_delete')

            return respone

        raise PermissionDenied


class BookUserList(generics.ListAPIView):
    """
    API endpoint that lists users of a specific book.
    """

    model = User
    serializer_class = serializers.BookUserListSerializer
    filter_class = BookUserListFilter

    def __init__(self):
        super(BookUserList, self).__init__()
        self._book = None

    def _get_book(self):
        try:
            self._book = Book.objects.get(id=self.kwargs.get('pk', None))
        except Book.DoesNotExist:
            raise NotFound

        return self._book

    def get_queryset(self):
        member_ids = [i[0] for i in BookRole.objects.filter(book=self._book).values_list('members')]

        return User.objects.filter(id__in=member_ids).order_by('username')

    def get(self, request, *args, **kwargs):
        book_security = BookSecurity(request.user, self._get_book())

        if book_security.has_perm('api.manage_books'):
            return super(BookUserList, self).get(request, *args, **kwargs)

        raise PermissionDenied


class BookUserDetailRoles(views.APIView):
    def get(self, request, book_id, pk, format=None):
        try:
            book = Book.objects.get(id=book_id)
            user = User.objects.get(id=pk)
        except (Book.DoesNotExist, User.DoesNotExist):
            raise NotFound

        book_security = BookSecurity(request.user, book)

        if not book_security.has_perm('api.manage_books'):
            raise PermissionDenied

        roles = {'default_roles': [], 'book_roles': []}

        # default roles
        roles['default_roles'].append(core_serializers.SimpleRoleSerializer(
            Role.objects.get(name='registered_users')
        ).data)

        print Role.objects.get(name='registered_users').permissions

        # get book roles
        for role in user.roles.filter(book=book):
            roles['book_roles'].append(core_serializers.SimpleBookRoleSerializer(role).data)

        return Response(roles)


class BookUserDetailPermissions(views.APIView):
    def get(self, request, book_id, pk, format=None):
        try:
            book = Book.objects.get(id=book_id)
            user = User.objects.get(id=pk)
        except (Book.DoesNotExist, User.DoesNotExist):
            raise NotFound

        book_security = BookSecurity(request.user, book)

        if not book_security.has_perm('api.manage_books'):
            raise PermissionDenied

        permissions = set()

        # default permissions
        for perm in Role.objects.get(name='registered_users').permissions.all():
            permissions.add('{}.{}'.format(perm.app_name, perm.name))

        # get book permissions
        for book_role in user.roles.filter(book=book):
            for perm in book_role.role.permissions.all():
                permissions.add('{}.{}'.format(perm.app_name, perm.name))

        permissions = list(permissions)
        permissions.sort()

        return Response(permissions)
