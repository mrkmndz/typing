import abc
import collections
import contextlib
import sys
import typing
import collections.abc as collections_abc
import operator

# After PEP 560, internal typing API was substantially reworked.
# This is especially important for Protocol class which uses internal APIs
# quite extensivelly.
PEP_560 = sys.version_info[:3] >= (3, 7, 0)

# These are used by Protocol implementation
# We use internal typing helpers here, but this significantly reduces
# code duplication. (Also this is only until Protocol is in typing.)
from typing import Generic, Callable, TypeVar, Tuple
if PEP_560:
    GenericMeta = TypingMeta = type
else:
    from typing import GenericMeta, TypingMeta
OLD_GENERICS = False
try:
    from typing import _type_vars, _next_in_mro, _type_check
except ImportError:
    OLD_GENERICS = True
try:
    from typing import _tp_cache
except ImportError:
    _tp_cache = lambda x: x
try:
    from typing import _TypingEllipsis, _TypingEmpty
except ImportError:
    class _TypingEllipsis: pass
    class _TypingEmpty: pass


# The two functions below are copies of typing internal helpers.
# They are needed by _ProtocolMeta


def _no_slots_copy(dct):
    dict_copy = dict(dct)
    if '__slots__' in dict_copy:
        for slot in dict_copy['__slots__']:
            dict_copy.pop(slot, None)
    return dict_copy


def _check_generic(cls, parameters):
    if not cls.__parameters__:
        raise TypeError("%s is not a generic class" % repr(cls))
    alen = len(parameters)
    elen = len(cls.__parameters__)
    if alen != elen:
        raise TypeError("Too %s parameters for %s; actual %s, expected %s" %
                        ("many" if alen > elen else "few", repr(cls), alen, elen))


if hasattr(typing, '_generic_new'):
    _generic_new = typing._generic_new
else:
    # Note: The '_generic_new(...)' function is used as a part of the
    # process of creating a generic type and was added to the typing module
    # as of Python 3.5.3.
    #
    # We've defined '_generic_new(...)' below to exactly match the behavior
    # implemented in older versions of 'typing' bundled with Python 3.5.0 to
    # 3.5.2. This helps eliminate redundancy when defining collection types
    # like 'Deque' later.
    #
    # See https://github.com/python/typing/pull/308 for more details -- in
    # particular, compare and contrast the definition of types like
    # 'typing.List' before and after the merge.

    def _generic_new(base_cls, cls, *args, **kwargs):
        return base_cls.__new__(cls, *args, **kwargs)

# See https://github.com/python/typing/pull/439
if hasattr(typing, '_geqv'):
    from typing import _geqv
    _geqv_defined = True
else:
    _geqv = None
    _geqv_defined = False

if sys.version_info[:2] >= (3, 6):
    import _collections_abc
    _check_methods_in_mro = _collections_abc._check_methods
else:
    def _check_methods_in_mro(C, *methods):
        mro = C.__mro__
        for method in methods:
            for B in mro:
                if method in B.__dict__:
                    if B.__dict__[method] is None:
                        return NotImplemented
                    break
            else:
                return NotImplemented
        return True


# Please keep __all__ alphabetized within each category.
__all__ = [
    # Super-special typing primitives.
    'ClassVar',
    'Final',
    'Type',

    # ABCs (from collections.abc).
    # The following are added depending on presence
    # of their non-generic counterparts in stdlib:
    # 'Awaitable',
    # 'AsyncIterator',
    # 'AsyncIterable',
    # 'Coroutine',
    # 'AsyncGenerator',
    # 'AsyncContextManager',
    # 'ChainMap',

    # Concrete collection types.
    'ContextManager',
    'Counter',
    'Deque',
    'DefaultDict',

    # One-off things.
    'CallableParametersVariable'
    'final',
    'IntVar',
    'Literal',
    'NewType',
    'overload',
    'Text',
    'TYPE_CHECKING',
]

# Protocols are hard to backport to the original version of typing 3.5.0
HAVE_PROTOCOLS = sys.version_info[:3] != (3, 5, 0)

if HAVE_PROTOCOLS:
    __all__.extend(['Protocol', 'runtime'])

# Annotations were implemented under tight time constraints; this keeps the
# implementation simple for now
HAVE_ANNOTATED = PEP_560

if HAVE_ANNOTATED:
    __all__.extend(['Annotated', 'get_type_hints'])


# TODO
if hasattr(typing, 'NoReturn'):
    NoReturn = typing.NoReturn
elif hasattr(typing, '_FinalTypingBase'):
    class _NoReturn(typing._FinalTypingBase, _root=True):
        """Special type indicating functions that never return.
        Example::

          from typing import NoReturn

          def stop() -> NoReturn:
              raise Exception('no way')

        This type is invalid in other positions, e.g., ``List[NoReturn]``
        will fail in static type checkers.
        """
        __slots__ = ()

        def __instancecheck__(self, obj):
            raise TypeError("NoReturn cannot be used with isinstance().")

        def __subclasscheck__(self, cls):
            raise TypeError("NoReturn cannot be used with issubclass().")

    NoReturn = _NoReturn(_root=True)
else:
    class _NoReturnMeta(typing.TypingMeta):
        """Metaclass for NoReturn"""
        def __new__(cls, name, bases, namespace, _root=False):
            return super().__new__(cls, name, bases, namespace, _root=_root)

        def __instancecheck__(self, obj):
            raise TypeError("NoReturn cannot be used with isinstance().")

        def __subclasscheck__(self, cls):
            raise TypeError("NoReturn cannot be used with issubclass().")

    class NoReturn(typing.Final, metaclass=_NoReturnMeta, _root=True):
        """Special type indicating functions that never return.
        Example::

          from typing import NoReturn

          def stop() -> NoReturn:
              raise Exception('no way')

        This type is invalid in other positions, e.g., ``List[NoReturn]``
        will fail in static type checkers.
        """
        __slots__ = ()


# Some unconstrained type variables.  These are used by the container types.
# (These are not for export.)
T = typing.TypeVar('T')  # Any type.
KT = typing.TypeVar('KT')  # Key type.
VT = typing.TypeVar('VT')  # Value type.
T_co = typing.TypeVar('T_co', covariant=True)  # Any type covariant containers.
V_co = typing.TypeVar('V_co', covariant=True)  # Any type covariant containers.
VT_co = typing.TypeVar('VT_co', covariant=True)  # Value type covariant containers.
T_contra = typing.TypeVar('T_contra', contravariant=True)  # Ditto contravariant.


def CallableParametersVariable(name):
    """This kind of type variable captures callable parameter specifications
    instead of types, allowing the typing of decorators which transform the 
    return type of the given callable.  For example:

        from typing import TypeVar, Callable, List
        from typing_extensions import CallableParametersVariable
        Tparams = CallableParametersVariable("Tparams")
        Treturn = TypeVar("Treturn")

        def unwrap(
            f: Callable[Tparams, List[Treturn],
        ) -> Callable[Tparams, Treturn]: ...

        @unwrap
        def foo(x: int, y: str, z: bool = False) -> List[int]:
            return [1, 2, 3]

    decorates foo into a callable that returns int, but still has the same 
    parameters, including their names and whether they are required.
    
    The empty list is required for backwards compatibility with the runtime 
    implementation for callables, which requires the first argument to be 
    a list of types
    """
    return []


if hasattr(typing, 'ClassVar'):
    ClassVar = typing.ClassVar
elif hasattr(typing, '_FinalTypingBase'):
    class _ClassVar(typing._FinalTypingBase, _root=True):
        """Special type construct to mark class variables.

        An annotation wrapped in ClassVar indicates that a given
        attribute is intended to be used as a class variable and
        should not be set on instances of that class. Usage::

          class Starship:
              stats: ClassVar[Dict[str, int]] = {} # class variable
              damage: int = 10                     # instance variable

        ClassVar accepts only types and cannot be further subscribed.

        Note that ClassVar is not a class itself, and should not
        be used with isinstance() or issubclass().
        """

        __slots__ = ('__type__',)

        def __init__(self, tp=None, **kwds):
            self.__type__ = tp

        def __getitem__(self, item):
            cls = type(self)
            if self.__type__ is None:
                return cls(typing._type_check(item,
                           '{} accepts only single type.'.format(cls.__name__[1:])),
                           _root=True)
            raise TypeError('{} cannot be further subscripted'
                            .format(cls.__name__[1:]))

        def _eval_type(self, globalns, localns):
            new_tp = typing._eval_type(self.__type__, globalns, localns)
            if new_tp == self.__type__:
                return self
            return type(self)(new_tp, _root=True)

        def __repr__(self):
            r = super().__repr__()
            if self.__type__ is not None:
                r += '[{}]'.format(typing._type_repr(self.__type__))
            return r

        def __hash__(self):
            return hash((type(self).__name__, self.__type__))

        def __eq__(self, other):
            if not isinstance(other, _ClassVar):
                return NotImplemented
            if self.__type__ is not None:
                return self.__type__ == other.__type__
            return self is other

    ClassVar = _ClassVar(_root=True)
else:
    class _ClassVarMeta(typing.TypingMeta):
        """Metaclass for ClassVar"""

        def __new__(cls, name, bases, namespace, tp=None, _root=False):
            self = super().__new__(cls, name, bases, namespace, _root=_root)
            if tp is not None:
                self.__type__ = tp
            return self

        def __instancecheck__(self, obj):
            raise TypeError("ClassVar cannot be used with isinstance().")

        def __subclasscheck__(self, cls):
            raise TypeError("ClassVar cannot be used with issubclass().")

        def __getitem__(self, item):
            cls = type(self)
            if self.__type__ is not None:
                raise TypeError('{} cannot be further subscripted'
                                .format(cls.__name__[1:]))

            param = typing._type_check(
                item,
                '{} accepts only single type.'.format(cls.__name__[1:]))
            return cls(self.__name__, self.__bases__,
                       dict(self.__dict__), tp=param, _root=True)

        def _eval_type(self, globalns, localns):
            new_tp = typing._eval_type(self.__type__, globalns, localns)
            if new_tp == self.__type__:
                return self
            return type(self)(self.__name__, self.__bases__,
                              dict(self.__dict__), tp=self.__type__,
                              _root=True)

        def __repr__(self):
            r = super().__repr__()
            if self.__type__ is not None:
                r += '[{}]'.format(typing._type_repr(self.__type__))
            return r

        def __hash__(self):
            return hash((type(self).__name__, self.__type__))

        def __eq__(self, other):
            if not isinstance(other, ClassVar):
                return NotImplemented
            if self.__type__ is not None:
                return self.__type__ == other.__type__
            return self is other

    class ClassVar(typing.Final, metaclass=_ClassVarMeta, _root=True):
        """Special type construct to mark class variables.

        An annotation wrapped in ClassVar indicates that a given
        attribute is intended to be used as a class variable and
        should not be set on instances of that class. Usage::

          class Starship:
              stats: ClassVar[Dict[str, int]] = {} # class variable
              damage: int = 10                     # instance variable

        ClassVar accepts only types and cannot be further subscribed.

        Note that ClassVar is not a class itself, and should not
        be used with isinstance() or issubclass().
        """

        __type__ = None

if sys.version_info[:2] >= (3, 7):
    class _FinalForm(typing._SpecialForm, _root=True):

        def __repr__(self):
            return 'typing_extensions.' + self._name

        def __getitem__(self, parameters):
            item = _type_check(parameters,
                               '{} accepts only single type'.format(self._name))
            return _GenericAlias(self, (item,))

    Final = _FinalForm('Final', doc=
        """A special typing construct to indicate that a name
        cannot be re-assigned or overridden in a subclass.
        For example:

            MAX_SIZE: Final = 9000
            MAX_SIZE += 1  # Error reported by type checker

            class Connection:
                TIMEOUT: Final[int] = 10
            class FastConnector(Connection):
                TIMEOUT = 1  # Error reported by type checker

        There is no runtime checking of these properties.
        """)
elif hasattr(typing, '_FinalTypingBase'):
    class _Final(typing._FinalTypingBase, _root=True):
        """A special typing construct to indicate that a name
        cannot be re-assigned or overridden in a subclass.
        For example:

            MAX_SIZE: Final = 9000
            MAX_SIZE += 1  # Error reported by type checker

            class Connection:
                TIMEOUT: Final[int] = 10
            class FastConnector(Connection):
                TIMEOUT = 1  # Error reported by type checker

        There is no runtime checking of these properties.
        """

        __slots__ = ('__type__',)

        def __init__(self, tp=None, **kwds):
            self.__type__ = tp

        def __getitem__(self, item):
            cls = type(self)
            if self.__type__ is None:
                return cls(typing._type_check(item,
                           '{} accepts only single type.'.format(cls.__name__[1:])),
                           _root=True)
            raise TypeError('{} cannot be further subscripted'
                            .format(cls.__name__[1:]))

        def _eval_type(self, globalns, localns):
            new_tp = typing._eval_type(self.__type__, globalns, localns)
            if new_tp == self.__type__:
                return self
            return type(self)(new_tp, _root=True)

        def __repr__(self):
            r = super().__repr__()
            if self.__type__ is not None:
                r += '[{}]'.format(typing._type_repr(self.__type__))
            return r

        def __hash__(self):
            return hash((type(self).__name__, self.__type__))

        def __eq__(self, other):
            if not isinstance(other, _Final):
                return NotImplemented
            if self.__type__ is not None:
                return self.__type__ == other.__type__
            return self is other

    Final = _Final(_root=True)
else:
    class _FinalMeta(typing.TypingMeta):
        """Metaclass for Final"""

        def __new__(cls, name, bases, namespace, tp=None, _root=False):
            self = super().__new__(cls, name, bases, namespace, _root=_root)
            if tp is not None:
                self.__type__ = tp
            return self

        def __instancecheck__(self, obj):
            raise TypeError("Final cannot be used with isinstance().")

        def __subclasscheck__(self, cls):
            raise TypeError("Final cannot be used with issubclass().")

        def __getitem__(self, item):
            cls = type(self)
            if self.__type__ is not None:
                raise TypeError('{} cannot be further subscripted'
                                .format(cls.__name__[1:]))

            param = typing._type_check(
                item,
                '{} accepts only single type.'.format(cls.__name__[1:]))
            return cls(self.__name__, self.__bases__,
                       dict(self.__dict__), tp=param, _root=True)

        def _eval_type(self, globalns, localns):
            new_tp = typing._eval_type(self.__type__, globalns, localns)
            if new_tp == self.__type__:
                return self
            return type(self)(self.__name__, self.__bases__,
                              dict(self.__dict__), tp=self.__type__,
                              _root=True)

        def __repr__(self):
            r = super().__repr__()
            if self.__type__ is not None:
                r += '[{}]'.format(typing._type_repr(self.__type__))
            return r

        def __hash__(self):
            return hash((type(self).__name__, self.__type__))

        def __eq__(self, other):
            if not isinstance(other, Final):
                return NotImplemented
            if self.__type__ is not None:
                return self.__type__ == other.__type__
            return self is other

    class Final(typing.Final, metaclass=_FinalMeta, _root=True):
        """A special typing construct to indicate that a name
        cannot be re-assigned or overridden in a subclass.
        For example:

            MAX_SIZE: Final = 9000
            MAX_SIZE += 1  # Error reported by type checker

            class Connection:
                TIMEOUT: Final[int] = 10
            class FastConnector(Connection):
                TIMEOUT = 1  # Error reported by type checker

        There is no runtime checking of these properties.
        """

        __type__ = None


def final(f):
    """This decorator can be used to indicate to type checkers that
    the decorated method cannot be overridden, and decorated class
    cannot be subclassed. For example:

        class Base:
            @final
            def done(self) -> None:
                ...
        class Sub(Base):
            def done(self) -> None:  # Error reported by type checker
                ...
        @final
        class Leaf:
            ...
        class Other(Leaf):  # Error reported by type checker
            ...

    There is no runtime checking of these properties.
    """
    return f


def IntVar(name):
    return TypeVar(name)


if hasattr(typing, 'Literal'):
    Literal = typing.Literal 
elif sys.version_info[:2] >= (3, 7):
    class _LiteralForm(typing._SpecialForm, _root=True):

        def __repr__(self):
            return 'typing_extensions.' + self._name

        def __getitem__(self, parameters):
            return _GenericAlias(self, parameters)

    Literal = _LiteralForm('Literal', doc=
        """A type that can be used to indicate to type checkers that the
        corresponding value has a value literally equivalent to the
        provided parameter. For example:

            var: Literal[4] = 4
        
        The type checker understands that 'var' is literally equal to the
        value 4 and no other value.

        Literal[...] cannot be subclassed. There is no runtime checking
        verifying that the parameter is actually a value instead of a type.
        """)
elif hasattr(typing, '_FinalTypingBase'):
    class _Literal(typing._FinalTypingBase, _root=True):
        """A type that can be used to indicate to type checkers that the
        corresponding value has a value literally equivalent to the
        provided parameter. For example:

            var: Literal[4] = 4
        
        The type checker understands that 'var' is literally equal to the
        value 4 and no other value.

        Literal[...] cannot be subclassed. There is no runtime checking
        verifying that the parameter is actually a value instead of a type.
        """

        __slots__ = ('__values__',)

        def __init__(self, values=None, **kwds):
            self.__values__ = values

        def __getitem__(self, values):
            cls = type(self)
            if self.__values__ is None:
                if not isinstance(values, tuple):
                    values = (values,)
                return cls(values, _root=True)
            raise TypeError('{} cannot be further subscripted'
                            .format(cls.__name__[1:]))

        def _eval_type(self, globalns, localns):
            return self

        def __repr__(self):
            r = super().__repr__()
            if self.__values__ is not None:
                r += '[{}]'.format(', '.join(map(typing._type_repr, self.__values__)))
            return r

        def __hash__(self):
            return hash((type(self).__name__, self.__values__))

        def __eq__(self, other):
            if not isinstance(other, _Literal):
                return NotImplemented
            if self.__values__ is not None:
                return self.__values__ == other.__values__
            return self is other

    Literal = _Literal(_root=True)
else:
    class _LiteralMeta(typing.TypingMeta):
        """Metaclass for Literal"""

        def __new__(cls, name, bases, namespace, values=None, _root=False):
            self = super().__new__(cls, name, bases, namespace, _root=_root)
            if values is not None:
                self.__values__ = values
            return self

        def __instancecheck__(self, obj):
            raise TypeError("Literal cannot be used with isinstance().")

        def __subclasscheck__(self, cls):
            raise TypeError("Literal cannot be used with issubclass().")

        def __getitem__(self, item):
            cls = type(self)
            if self.__values__ is not None:
                raise TypeError('{} cannot be further subscripted'
                                .format(cls.__name__[1:]))

            if not isinstance(item, tuple):
                item = (item,)
            return cls(self.__name__, self.__bases__,
                       dict(self.__dict__), values=item, _root=True)

        def _eval_type(self, globalns, localns):
            return self

        def __repr__(self):
            r = super().__repr__()
            if self.__values__ is not None:
                r += '[{}]'.format(', '.join(map(typing._type_repr, self.__values__)))
            return r

        def __hash__(self):
            return hash((type(self).__name__, self.__values__))

        def __eq__(self, other):
            if not isinstance(other, Literal):
                return NotImplemented
            if self.__values__ is not None:
                return self.__values__ == other.__values__
            return self is other

    class Literal(typing.Final, metaclass=_LiteralMeta, _root=True):
        """A type that can be used to indicate to type checkers that the
        corresponding value has a value literally equivalent to the
        provided parameter. For example:

            var: Literal[4] = 4
        
        The type checker understands that 'var' is literally equal to the
        value 4 and no other value.

        Literal[...] cannot be subclassed. There is no runtime checking
        verifying that the parameter is actually a value instead of a type.
        """

        __values__ = None


def _overload_dummy(*args, **kwds):
    """Helper for @overload to raise when called."""
    raise NotImplementedError(
        "You should not call an overloaded function. "
        "A series of @overload-decorated functions "
        "outside a stub module should always be followed "
        "by an implementation that is not @overload-ed.")


def overload(func):
    """Decorator for overloaded functions/methods.

    In a stub file, place two or more stub definitions for the same
    function in a row, each decorated with @overload.  For example:

      @overload
      def utf8(value: None) -> None: ...
      @overload
      def utf8(value: bytes) -> bytes: ...
      @overload
      def utf8(value: str) -> bytes: ...

    In a non-stub file (i.e. a regular .py file), do the same but
    follow it with an implementation.  The implementation should *not*
    be decorated with @overload.  For example:

      @overload
      def utf8(value: None) -> None: ...
      @overload
      def utf8(value: bytes) -> bytes: ...
      @overload
      def utf8(value: str) -> bytes: ...
      def utf8(value):
          # implementation goes here
    """
    return _overload_dummy


# This is not a real generic class.  Don't use outside annotations.
if hasattr(typing, 'Type'):
    Type = typing.Type
else:
    # Internal type variable used for Type[].
    CT_co = typing.TypeVar('CT_co', covariant=True, bound=type)

    class Type(typing.Generic[CT_co], extra=type):
        """A special construct usable to annotate class objects.

        For example, suppose we have the following classes::

          class User: ...  # Abstract base for User classes
          class BasicUser(User): ...
          class ProUser(User): ...
          class TeamUser(User): ...

        And a function that takes a class argument that's a subclass of
        User and returns an instance of the corresponding class::

          U = TypeVar('U', bound=User)
          def new_user(user_class: Type[U]) -> U:
              user = user_class()
              # (Here we could write the user object to a database)
              return user
          joe = new_user(BasicUser)

        At this point the type checker knows that joe has type BasicUser.
        """

        __slots__ = ()


# Various ABCs mimicking those in collections.abc.
# A few are simply re-exported for completeness.

def _define_guard(type_name):
    """
    Returns True if the given type isn't defined in typing but
    is defined in collections_abc.

    Adds the type to __all__ if the collection is found in either
    typing or collection_abc.
    """
    if hasattr(typing, type_name):
        __all__.append(type_name)
        globals()[type_name] = getattr(typing, type_name)
        return False
    elif hasattr(collections_abc, type_name):
        __all__.append(type_name)
        return True
    else:
        return False


class _ExtensionsGenericMeta(GenericMeta):
    def __subclasscheck__(self, subclass):
        """This mimics a more modern GenericMeta.__subclasscheck__() logic
        (that does not have problems with recursion) to work around interactions
        between collections, typing, and typing_extensions on older
        versions of Python, see https://github.com/python/typing/issues/501.
        """
        if sys.version_info[:3] >= (3, 5, 3) or sys.version_info[:3] < (3, 5, 0):
            if self.__origin__ is not None:
                if sys._getframe(1).f_globals['__name__'] not in ['abc', 'functools']:
                    raise TypeError("Parameterized generics cannot be used with class "
                                    "or instance checks")
                return False
        if not self.__extra__:
            return super().__subclasscheck__(subclass)
        res = self.__extra__.__subclasshook__(subclass)
        if res is not NotImplemented:
            return res
        if self.__extra__ in subclass.__mro__:
            return True
        for scls in self.__extra__.__subclasses__():
            if isinstance(scls, GenericMeta):
                continue
            if issubclass(subclass, scls):
                return True
        return False


if _define_guard('Awaitable'):
    class Awaitable(typing.Generic[T_co], metaclass=_ExtensionsGenericMeta,
                    extra=collections_abc.Awaitable):
        __slots__ = ()


if _define_guard('Coroutine'):
    class Coroutine(Awaitable[V_co], typing.Generic[T_co, T_contra, V_co],
                    metaclass=_ExtensionsGenericMeta,
                    extra=collections_abc.Coroutine):
        __slots__ = ()


if _define_guard('AsyncIterable'):
    class AsyncIterable(typing.Generic[T_co],
                        metaclass=_ExtensionsGenericMeta,
                        extra=collections_abc.AsyncIterable):
        __slots__ = ()


if _define_guard('AsyncIterator'):
    class AsyncIterator(AsyncIterable[T_co],
                        metaclass=_ExtensionsGenericMeta,
                        extra=collections_abc.AsyncIterator):
        __slots__ = ()


if hasattr(typing, 'Deque'):
    Deque = typing.Deque
elif _geqv_defined:
    class Deque(collections.deque, typing.MutableSequence[T],
                metaclass=_ExtensionsGenericMeta,
                extra=collections.deque):
        __slots__ = ()

        def __new__(cls, *args, **kwds):
            if _geqv(cls, Deque):
                return collections.deque(*args, **kwds)
            return _generic_new(collections.deque, cls, *args, **kwds)
else:
    class Deque(collections.deque, typing.MutableSequence[T],
                metaclass=_ExtensionsGenericMeta,
                extra=collections.deque):
        __slots__ = ()

        def __new__(cls, *args, **kwds):
            if cls._gorg is Deque:
                return collections.deque(*args, **kwds)
            return _generic_new(collections.deque, cls, *args, **kwds)


if hasattr(typing, 'ContextManager'):
    ContextManager = typing.ContextManager
elif hasattr(contextlib, 'AbstractContextManager'):
    class ContextManager(typing.Generic[T_co],
                         metaclass=_ExtensionsGenericMeta,
                         extra=contextlib.AbstractContextManager):
        __slots__ = ()
else:
    class ContextManager(typing.Generic[T_co]):
        __slots__ = ()

        def __enter__(self):
            return self

        @abc.abstractmethod
        def __exit__(self, exc_type, exc_value, traceback):
            return None

        @classmethod
        def __subclasshook__(cls, C):
            if cls is ContextManager:
                # In Python 3.6+, it is possible to set a method to None to
                # explicitly indicate that the class does not implement an ABC
                # (https://bugs.python.org/issue25958), but we do not support
                # that pattern here because this fallback class is only used
                # in Python 3.5 and earlier.
                if (any("__enter__" in B.__dict__ for B in C.__mro__) and
                    any("__exit__" in B.__dict__ for B in C.__mro__)):
                    return True
            return NotImplemented


if hasattr(typing, 'AsyncContextManager'):
    AsyncContextManager = typing.AsyncContextManager
    __all__.append('AsyncContextManager')
elif hasattr(contextlib, 'AbstractAsyncContextManager'):
    class AsyncContextManager(typing.Generic[T_co],
                              metaclass=_ExtensionsGenericMeta,
                              extra=contextlib.AbstractAsyncContextManager):
        __slots__ = ()

    __all__.append('AsyncContextManager')
elif sys.version_info[:2] >= (3, 5):
    exec("""
class AsyncContextManager(typing.Generic[T_co]):
    __slots__ = ()

    async def __aenter__(self):
        return self

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    @classmethod
    def __subclasshook__(cls, C):
        if cls is AsyncContextManager:
            return _check_methods_in_mro(C, "__aenter__", "__aexit__")
        return NotImplemented

__all__.append('AsyncContextManager')
""")


if hasattr(typing, 'DefaultDict'):
    DefaultDict = typing.DefaultDict
elif _geqv_defined:
    class DefaultDict(collections.defaultdict, typing.MutableMapping[KT, VT],
                      metaclass=_ExtensionsGenericMeta,
                      extra=collections.defaultdict):

        __slots__ = ()

        def __new__(cls, *args, **kwds):
            if _geqv(cls, DefaultDict):
                return collections.defaultdict(*args, **kwds)
            return _generic_new(collections.defaultdict, cls, *args, **kwds)
else:
    class DefaultDict(collections.defaultdict, typing.MutableMapping[KT, VT],
                      metaclass=_ExtensionsGenericMeta,
                      extra=collections.defaultdict):

        __slots__ = ()

        def __new__(cls, *args, **kwds):
            if cls._gorg is DefaultDict:
                return collections.defaultdict(*args, **kwds)
            return _generic_new(collections.defaultdict, cls, *args, **kwds)


if hasattr(typing, 'Counter'):
    Counter = typing.Counter
elif (3, 5, 0) <= sys.version_info[:3] <= (3, 5, 1):
    assert _geqv_defined
    _TInt = typing.TypeVar('_TInt')

    class _CounterMeta(typing.GenericMeta):
        """Metaclass for Counter"""
        def __getitem__(self, item):
            return super().__getitem__((item, int))

    class Counter(collections.Counter,
                  typing.Dict[T, int],
                  metaclass=_CounterMeta,
                  extra=collections.Counter):

        __slots__ = ()

        def __new__(cls, *args, **kwds):
            if _geqv(cls, Counter):
                return collections.Counter(*args, **kwds)
            return _generic_new(collections.Counter, cls, *args, **kwds)

elif _geqv_defined:
    class Counter(collections.Counter,
                  typing.Dict[T, int],
                  metaclass=_ExtensionsGenericMeta, extra=collections.Counter):

        __slots__ = ()

        def __new__(cls, *args, **kwds):
            if _geqv(cls, Counter):
                return collections.Counter(*args, **kwds)
            return _generic_new(collections.Counter, cls, *args, **kwds)

else:
    class Counter(collections.Counter,
                  typing.Dict[T, int],
                  metaclass=_ExtensionsGenericMeta, extra=collections.Counter):

        __slots__ = ()

        def __new__(cls, *args, **kwds):
            if cls._gorg is Counter:
                return collections.Counter(*args, **kwds)
            return _generic_new(collections.Counter, cls, *args, **kwds)


if hasattr(typing, 'ChainMap'):
    ChainMap = typing.ChainMap
    __all__.append('ChainMap')
elif hasattr(collections, 'ChainMap'):
    # ChainMap only exists in 3.3+
    if _geqv_defined:
        class ChainMap(collections.ChainMap, typing.MutableMapping[KT, VT],
                       metaclass=_ExtensionsGenericMeta,
                       extra=collections.ChainMap):

            __slots__ = ()

            def __new__(cls, *args, **kwds):
                if _geqv(cls, ChainMap):
                    return collections.ChainMap(*args, **kwds)
                return _generic_new(collections.ChainMap, cls, *args, **kwds)
    else:
        class ChainMap(collections.ChainMap, typing.MutableMapping[KT, VT],
                       metaclass=_ExtensionsGenericMeta,
                       extra=collections.ChainMap):

            __slots__ = ()

            def __new__(cls, *args, **kwds):
                if cls._gorg is ChainMap:
                    return collections.ChainMap(*args, **kwds)
                return _generic_new(collections.ChainMap, cls, *args, **kwds)

    __all__.append('ChainMap')


if _define_guard('AsyncGenerator'):
    class AsyncGenerator(AsyncIterator[T_co], typing.Generic[T_co, T_contra],
                         metaclass=_ExtensionsGenericMeta,
                         extra=collections_abc.AsyncGenerator):
        __slots__ = ()


if hasattr(typing, 'NewType'):
    NewType = typing.NewType
else:
    def NewType(name, tp):
        """NewType creates simple unique types with almost zero
        runtime overhead. NewType(name, tp) is considered a subtype of tp
        by static type checkers. At runtime, NewType(name, tp) returns
        a dummy function that simply returns its argument. Usage::

            UserId = NewType('UserId', int)

            def name_by_id(user_id: UserId) -> str:
                ...

            UserId('user')          # Fails type check

            name_by_id(42)          # Fails type check
            name_by_id(UserId(42))  # OK

            num = UserId(5) + 1     # type: int
        """

        def new_type(x):
            return x

        new_type.__name__ = name
        new_type.__supertype__ = tp
        return new_type


if hasattr(typing, 'Text'):
    Text = typing.Text
else:
    Text = str


if hasattr(typing, 'TYPE_CHECKING'):
    TYPE_CHECKING = typing.TYPE_CHECKING
else:
    # Constant that's True when type checking, but False here.
    TYPE_CHECKING = False


def _gorg(cls):
    """This function exists for compatibility with old typing versions."""
    assert isinstance(cls, GenericMeta)
    if hasattr(cls, '_gorg'):
        return cls._gorg
    while cls.__origin__ is not None:
        cls = cls.__origin__
    return cls


if OLD_GENERICS:
    def _next_in_mro(cls):
        """This function exists for compatibility with old typing versions."""
        next_in_mro = object
        for i, c in enumerate(cls.__mro__[:-1]):
            if isinstance(c, GenericMeta) and _gorg(c) is Generic:
                next_in_mro = cls.__mro__[i + 1]
        return next_in_mro


def _get_protocol_attrs(cls):
    attrs = set()
    for base in cls.__mro__[:-1]:  # without object
        if base.__name__ in ('Protocol', 'Generic'):
            continue
        annotations = getattr(base, '__annotations__', {})
        for attr in list(base.__dict__.keys()) + list(annotations.keys()):
            if (not attr.startswith('_abc_') and attr not in (
                    '__abstractmethods__', '__annotations__', '__weakref__',
                    '_is_protocol', '_is_runtime_protocol', '__dict__',
                    '__args__', '__slots__',
                    '__next_in_mro__', '__parameters__', '__origin__',
                    '__orig_bases__', '__extra__', '__tree_hash__',
                    '__doc__', '__subclasshook__', '__init__', '__new__',
                    '__module__', '_MutableMapping__marker', '_gorg')):
                attrs.add(attr)
    return attrs


def _is_callable_members_only(cls):
    return all(callable(getattr(cls, attr, None)) for attr in _get_protocol_attrs(cls))


if HAVE_PROTOCOLS and not PEP_560:
    class _ProtocolMeta(GenericMeta):
        """Internal metaclass for Protocol.

        This exists so Protocol classes can be generic without deriving
        from Generic.
        """
        if not OLD_GENERICS:
            def __new__(cls, name, bases, namespace,
                        tvars=None, args=None, origin=None, extra=None, orig_bases=None):
                # This is just a version copied from GenericMeta.__new__ that
                # includes "Protocol" special treatment. (Comments removed for brevity.)
                assert extra is None  # Protocols should not have extra
                if tvars is not None:
                    assert origin is not None
                    assert all(isinstance(t, TypeVar) for t in tvars), tvars
                else:
                    tvars = _type_vars(bases)
                    gvars = None
                    for base in bases:
                        if base is Generic:
                            raise TypeError("Cannot inherit from plain Generic")
                        if (isinstance(base, GenericMeta) and
                                base.__origin__ in (Generic, Protocol)):
                            if gvars is not None:
                                raise TypeError(
                                    "Cannot inherit from Generic[...] or"
                                    " Protocol[...] multiple times.")
                            gvars = base.__parameters__
                    if gvars is None:
                        gvars = tvars
                    else:
                        tvarset = set(tvars)
                        gvarset = set(gvars)
                        if not tvarset <= gvarset:
                            raise TypeError(
                                "Some type variables (%s) "
                                "are not listed in %s[%s]" %
                                (", ".join(str(t) for t in tvars if t not in gvarset),
                                 "Generic" if any(b.__origin__ is Generic
                                                  for b in bases) else "Protocol",
                                 ", ".join(str(g) for g in gvars)))
                        tvars = gvars

                initial_bases = bases
                if (extra is not None and type(extra) is abc.ABCMeta and
                        extra not in bases):
                    bases = (extra,) + bases
                bases = tuple(_gorg(b) if isinstance(b, GenericMeta) else b
                              for b in bases)
                if any(isinstance(b, GenericMeta) and b is not Generic for b in bases):
                    bases = tuple(b for b in bases if b is not Generic)
                namespace.update({'__origin__': origin, '__extra__': extra})
                self = super(GenericMeta, cls).__new__(cls, name, bases, namespace,
                                                       _root=True)
                super(GenericMeta, self).__setattr__('_gorg',
                                                     self if not origin else
                                                     _gorg(origin))
                self.__parameters__ = tvars
                self.__args__ = tuple(... if a is _TypingEllipsis else
                                      () if a is _TypingEmpty else
                                      a for a in args) if args else None
                self.__next_in_mro__ = _next_in_mro(self)
                if orig_bases is None:
                    self.__orig_bases__ = initial_bases
                elif origin is not None:
                    self._abc_registry = origin._abc_registry
                    self._abc_cache = origin._abc_cache
                if hasattr(self, '_subs_tree'):
                    self.__tree_hash__ = (hash(self._subs_tree()) if origin else
                                          super(GenericMeta, self).__hash__())
                return self

        def __init__(cls, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if not cls.__dict__.get('_is_protocol', None):
                cls._is_protocol = any(b is Protocol or
                                       isinstance(b, _ProtocolMeta) and
                                       b.__origin__ is Protocol
                                       for b in cls.__bases__)
            if cls._is_protocol:
                for base in cls.__mro__[1:]:
                    if not (base in (object, Generic, Callable) or
                            isinstance(base, TypingMeta) and base._is_protocol or
                            isinstance(base, GenericMeta) and
                            base.__origin__ is Generic):
                        raise TypeError('Protocols can only inherit from other'
                                        ' protocols, got %r' % base)

                def _no_init(self, *args, **kwargs):
                    if type(self)._is_protocol:
                        raise TypeError('Protocols cannot be instantiated')
                cls.__init__ = _no_init

            def _proto_hook(other):
                if not cls.__dict__.get('_is_protocol', None):
                    return NotImplemented
                if not isinstance(other, type):
                    # Same error as for issubclass(1, int)
                    raise TypeError('issubclass() arg 1 must be a class')
                for attr in _get_protocol_attrs(cls):
                    for base in other.__mro__:
                        if attr in base.__dict__:
                            if base.__dict__[attr] is None:
                                return NotImplemented
                            break
                        annotations = getattr(base, '__annotations__', {})
                        if (isinstance(annotations, typing.Mapping) and attr in annotations and
                                isinstance(other, _ProtocolMeta) and other._is_protocol):
                            break
                    else:
                        return NotImplemented
                return True
            if '__subclasshook__' not in cls.__dict__:
                cls.__subclasshook__ = _proto_hook

        def __instancecheck__(self, instance):
            # We need this method for situations where attributes are
            # assigned in __init__.
            if ((not getattr(self, '_is_protocol', False) or
                    _is_callable_members_only(self)) and
                    issubclass(instance.__class__, self)):
                return True
            if self._is_protocol:
                if all(hasattr(instance, attr) and
                        (not callable(getattr(self, attr, None)) or
                         getattr(instance, attr) is not None)
                        for attr in _get_protocol_attrs(self)):
                    return True
            return super(GenericMeta, self).__instancecheck__(instance)

        def __subclasscheck__(self, cls):
            if self.__origin__ is not None:
                if sys._getframe(1).f_globals['__name__'] not in ['abc', 'functools']:
                    raise TypeError("Parameterized generics cannot be used with class "
                                    "or instance checks")
                return False
            if (self.__dict__.get('_is_protocol', None) and
                    not self.__dict__.get('_is_runtime_protocol', None)):
                if sys._getframe(1).f_globals['__name__'] in ['abc', 'functools', 'typing']:
                    return False
                raise TypeError("Instance and class checks can only be used with"
                                " @runtime protocols")
            if (self.__dict__.get('_is_runtime_protocol', None) and
                    not _is_callable_members_only(self)):
                if sys._getframe(1).f_globals['__name__'] in ['abc', 'functools', 'typing']:
                    return super(GenericMeta, self).__subclasscheck__(cls)
                raise TypeError("Protocols with non-method members"
                                " don't support issubclass()")
            return super(GenericMeta, self).__subclasscheck__(cls)

        if not OLD_GENERICS:
            @_tp_cache
            def __getitem__(self, params):
                # We also need to copy this from GenericMeta.__getitem__ to get
                # special treatment of "Protocol". (Comments removed for brevity.)
                if not isinstance(params, tuple):
                    params = (params,)
                if not params and _gorg(self) is not Tuple:
                    raise TypeError(
                        "Parameter list to %s[...] cannot be empty" % self.__qualname__)
                msg = "Parameters to generic types must be types."
                params = tuple(_type_check(p, msg) for p in params)
                if self in (Generic, Protocol):
                    if not all(isinstance(p, TypeVar) for p in params):
                        raise TypeError(
                            "Parameters to %r[...] must all be type variables" % self)
                    if len(set(params)) != len(params):
                        raise TypeError(
                            "Parameters to %r[...] must all be unique" % self)
                    tvars = params
                    args = params
                elif self in (Tuple, Callable):
                    tvars = _type_vars(params)
                    args = params
                elif self.__origin__ in (Generic, Protocol):
                    raise TypeError("Cannot subscript already-subscripted %s" %
                                    repr(self))
                else:
                    _check_generic(self, params)
                    tvars = _type_vars(params)
                    args = params

                prepend = (self,) if self.__origin__ is None else ()
                return self.__class__(self.__name__,
                                      prepend + self.__bases__,
                                      _no_slots_copy(self.__dict__),
                                      tvars=tvars,
                                      args=args,
                                      origin=self,
                                      extra=self.__extra__,
                                      orig_bases=self.__orig_bases__)

    class Protocol(metaclass=_ProtocolMeta):
        """Base class for protocol classes. Protocol classes are defined as::

          class Proto(Protocol):
              def meth(self) -> int:
                  ...

        Such classes are primarily used with static type checkers that recognize
        structural subtyping (static duck-typing), for example::

          class C:
              def meth(self) -> int:
                  return 0

          def func(x: Proto) -> int:
              return x.meth()

          func(C())  # Passes static type check

        See PEP 544 for details. Protocol classes decorated with
        @typing_extensions.runtime act as simple-minded runtime protocol that checks
        only the presence of given attributes, ignoring their type signatures.

        Protocol classes can be generic, they are defined as::

          class GenProto({bases}):
              def meth(self) -> T:
                  ...
        """
        __slots__ = ()
        _is_protocol = True

        def __new__(cls, *args, **kwds):
            if _gorg(cls) is Protocol:
                raise TypeError("Type Protocol cannot be instantiated; "
                                "it can be used only as a base class")
            if OLD_GENERICS:
                return _generic_new(_next_in_mro(cls), cls, *args, **kwds)
            return _generic_new(cls.__next_in_mro__, cls, *args, **kwds)
    if Protocol.__doc__ is not None:
        Protocol.__doc__ = Protocol.__doc__.format(bases="Protocol, Generic[T]" if
                                                   OLD_GENERICS else "Protocol[T]")


elif PEP_560:
    from typing import _type_check, _GenericAlias, _collect_type_vars

    class _ProtocolMeta(abc.ABCMeta):
        # This metaclass is a bit unfortunate and exists only because of the lack
        # of __instancehook__.
        def __instancecheck__(cls, instance):
            # We need this method for situations where attributes are
            # assigned in __init__.
            if ((not getattr(cls, '_is_protocol', False) or
                    _is_callable_members_only(cls)) and
                    issubclass(instance.__class__, cls)):
                return True
            if cls._is_protocol:
                if all(hasattr(instance, attr) and
                        (not callable(getattr(cls, attr, None)) or
                         getattr(instance, attr) is not None)
                        for attr in _get_protocol_attrs(cls)):
                    return True
            return super().__instancecheck__(instance)


    class Protocol(metaclass=_ProtocolMeta):
        # There is quite a lot of overlapping code with typing.Generic.
        # Unfortunately it is hard to avoid this while these live in two different modules.
        # The duplicated code will be removed when Protocol is moved to typing.
        """Base class for protocol classes. Protocol classes are defined as::

            class Proto(Protocol):
                def meth(self) -> int:
                    ...

        Such classes are primarily used with static type checkers that recognize
        structural subtyping (static duck-typing), for example::

            class C:
                def meth(self) -> int:
                    return 0

            def func(x: Proto) -> int:
                return x.meth()

            func(C())  # Passes static type check

        See PEP 544 for details. Protocol classes decorated with
        @typing_extensions.runtime act as simple-minded runtime protocol that checks
        only the presence of given attributes, ignoring their type signatures.

        Protocol classes can be generic, they are defined as::

            class GenProto(Protocol[T]):
                def meth(self) -> T:
                    ...
        """
        __slots__ = ()
        _is_protocol = True

        def __new__(cls, *args, **kwds):
            if cls is Protocol:
                raise TypeError("Type Protocol cannot be instantiated; "
                                "it can only be used as a base class")
            return super().__new__(cls)

        @_tp_cache
        def __class_getitem__(cls, params):
            if not isinstance(params, tuple):
                params = (params,)
            if not params and cls is not Tuple:
                raise TypeError(
                    "Parameter list to {}[...] cannot be empty".format(cls.__qualname__))
            msg = "Parameters to generic types must be types."
            params = tuple(_type_check(p, msg) for p in params)
            if cls is Protocol:
                # Generic can only be subscripted with unique type variables.
                if not all(isinstance(p, TypeVar) for p in params):
                    i = 0
                    while isinstance(params[i], TypeVar):
                        i += 1
                    raise TypeError(
                        "Parameters to Protocol[...] must all be type variables."
                        " Parameter {} is {}".format(i + 1, params[i]))
                if len(set(params)) != len(params):
                    raise TypeError(
                        "Parameters to Protocol[...] must all be unique")
            else:
                # Subscripting a regular Generic subclass.
                _check_generic(cls, params)
            return _GenericAlias(cls, params)

        def __init_subclass__(cls, *args, **kwargs):
            tvars = []
            if '__orig_bases__' in cls.__dict__:
                error = Generic in cls.__orig_bases__
            else:
                error = Generic in cls.__bases__
            if error:
                raise TypeError("Cannot inherit from plain Generic")
            if '__orig_bases__' in cls.__dict__:
                tvars = _collect_type_vars(cls.__orig_bases__)
                # Look for Generic[T1, ..., Tn] or Protocol[T1, ..., Tn].
                # If found, tvars must be a subset of it.
                # If not found, tvars is it.
                # Also check for and reject plain Generic,
                # and reject multiple Generic[...] and/or Protocol[...].
                gvars = None
                for base in cls.__orig_bases__:
                    if (isinstance(base, _GenericAlias) and
                            base.__origin__ in (Generic, Protocol)):
                        # for error messages
                        the_base = 'Generic' if base.__origin__ is Generic else 'Protocol'
                        if gvars is not None:
                            raise TypeError(
                                "Cannot inherit from Generic[...]"
                                " and/or Protocol[...] multiple types.")
                        gvars = base.__parameters__
                if gvars is None:
                    gvars = tvars
                else:
                    tvarset = set(tvars)
                    gvarset = set(gvars)
                    if not tvarset <= gvarset:
                        s_vars = ', '.join(str(t) for t in tvars if t not in gvarset)
                        s_args = ', '.join(str(g) for g in gvars)
                        raise TypeError("Some type variables ({}) are"
                                        " not listed in {}[{}]".format(s_vars, the_base, s_args))
                    tvars = gvars
            cls.__parameters__ = tuple(tvars)

            # Determine if this is a protocol or a concrete subclass.
            if not cls.__dict__.get('_is_protocol', None):
                cls._is_protocol = any(b is Protocol for b in cls.__bases__)

            # Set (or override) the protocol subclass hook.
            def _proto_hook(other):
                if not cls.__dict__.get('_is_protocol', None):
                    return NotImplemented
                if not getattr(cls, '_is_runtime_protocol', False):
                    if sys._getframe(2).f_globals['__name__'] in ['abc', 'functools']:
                        return NotImplemented
                    raise TypeError("Instance and class checks can only be used with"
                                    " @runtime protocols")
                if not _is_callable_members_only(cls):
                    if sys._getframe(2).f_globals['__name__'] in ['abc', 'functools']:
                        return NotImplemented
                    raise TypeError("Protocols with non-method members"
                                    " don't support issubclass()")
                if not isinstance(other, type):
                    # Same error as for issubclass(1, int)
                    raise TypeError('issubclass() arg 1 must be a class')
                for attr in _get_protocol_attrs(cls):
                    for base in other.__mro__:
                        if attr in base.__dict__:
                            if base.__dict__[attr] is None:
                                return NotImplemented
                            break
                        annotations = getattr(base, '__annotations__', {})
                        if (isinstance(annotations, typing.Mapping) and attr in annotations and
                                isinstance(other, _ProtocolMeta) and other._is_protocol):
                            break
                    else:
                        return NotImplemented
                return True
            if '__subclasshook__' not in cls.__dict__:
                cls.__subclasshook__ = _proto_hook

            # We have nothing more to do for non-protocols.
            if not cls._is_protocol:
                return

            # Check consistency of bases.
            for base in cls.__bases__:
                if not (base in (object, Generic, Callable) or
                        isinstance(base, _ProtocolMeta) and base._is_protocol):
                    raise TypeError('Protocols can only inherit from other'
                                    ' protocols, got %r' % base)

            def _no_init(self, *args, **kwargs):
                if type(self)._is_protocol:
                    raise TypeError('Protocols cannot be instantiated')
            cls.__init__ = _no_init


if HAVE_PROTOCOLS:
    def runtime(cls):
        """Mark a protocol class as a runtime protocol, so that it
        can be used with isinstance() and issubclass(). Raise TypeError
        if applied to a non-protocol class.

        This allows a simple-minded structural check very similar to the
        one-offs in collections.abc such as Hashable.
        """
        if not isinstance(cls, _ProtocolMeta) or not cls._is_protocol:
            raise TypeError('@runtime can be only applied to protocol classes,'
                            ' got %r' % cls)
        cls._is_runtime_protocol = True
        return cls


def _check_fails(cls, other):
    try:
        if sys._getframe(1).f_globals['__name__'] not in ['abc', 'functools', 'typing']:
            # Typed dicts are only for static structural subtyping.
            raise TypeError('TypedDict does not support instance and class checks')
    except (AttributeError, ValueError):
        pass
    return False


def _dict_new(cls, *args, **kwargs):
    return dict(*args, **kwargs)


def _typeddict_new(cls, _typename, _fields=None, **kwargs):
    total = kwargs.pop('total', True)
    if _fields is None:
        _fields = kwargs
    elif kwargs:
        raise TypeError("TypedDict takes either a dict or keyword arguments,"
                        " but not both")

    ns = {'__annotations__': dict(_fields), '__total__': total}
    try:
        # Setting correct module is necessary to make typed dict classes pickleable.
        ns['__module__'] = sys._getframe(1).f_globals.get('__name__', '__main__')
    except (AttributeError, ValueError):
        pass

    return _TypedDictMeta(_typename, (), ns)


class _TypedDictMeta(type):
    def __new__(cls, name, bases, ns, total=True):
        # Create new typed dict class object.
        # This method is called directly when TypedDict is subclassed,
        # or via _typeddict_new when TypedDict is instantiated. This way
        # TypedDict supports all three syntaxes described in its docstring.
        # Subclasses and instances of TypedDict return actual dictionaries
        # via _dict_new.
        ns['__new__'] = _typeddict_new if name == 'TypedDict' else _dict_new
        tp_dict = super(_TypedDictMeta, cls).__new__(cls, name, (dict,), ns)

        anns = ns.get('__annotations__', {})
        msg = "TypedDict('Name', {f0: t0, f1: t1, ...}); each t must be a type"
        anns = {n: typing._type_check(tp, msg) for n, tp in anns.items()}
        for base in bases:
            anns.update(base.__dict__.get('__annotations__', {}))
        tp_dict.__annotations__ = anns
        if not hasattr(tp_dict, '__total__'):
            tp_dict.__total__ = total
        return tp_dict

    __instancecheck__ = __subclasscheck__ = _check_fails


TypedDict = _TypedDictMeta('TypedDict', (dict,), {})
TypedDict.__module__ = __name__
TypedDict.__doc__ = \
    """A simple typed name space. At runtime it is equivalent to a plain dict.

    TypedDict creates a dictionary type that expects all of its
    instances to have a certain set of keys, with each key
    associated with a value of a consistent type. This expectation
    is not checked at runtime but is only enforced by type checkers.
    Usage::

        class Point2D(TypedDict):
            x: int
            y: int
            label: str

        a: Point2D = {'x': 1, 'y': 2, 'label': 'good'}  # OK
        b: Point2D = {'z': 3, 'label': 'bad'}           # Fails type check

        assert Point2D(x=1, y=2, label='first') == dict(x=1, y=2, label='first')

    The type info could be accessed via Point2D.__annotations__. TypedDict
    supports two additional equivalent forms::

        Point2D = TypedDict('Point2D', x=int, y=int, label=str)
        Point2D = TypedDict('Point2D', {'x': int, 'y': int, 'label': str})

    The class syntax is only supported in Python 3.6+, while two other
    syntax forms work for Python 2.7 and 3.2+
    """


if HAVE_ANNOTATED:
    class _Annotated(typing._GenericAlias, _root=True):
        """Runtime representation of an annotated type.

        At its core 'Annotated[t, dec1, dec2, ...]' is an alias for the type 't'
        with extra annotations. The alias behaves like a normal typing alias,
        instantiating is the same as instantiating the underlying type, binding
        it to types is also the same.
        """
        def __init__(self, origin, metadata):
            if isinstance(origin, _Annotated):
                metadata = origin.__metadata__ + metadata
                origin = origin.__origin__
            super().__init__(origin, origin)
            self.__metadata__ = metadata

        def copy_with(self, params):
            assert len(params) == 1
            new_type = params[0]
            return _Annotated(new_type, self.__metadata__)

        def __repr__(self):
            return "typing_extensions.Annotated[{}, {}]".format(
                typing._type_repr(self.__origin__),
                ", ".join(repr(a) for a in self.__metadata__)
            )

        def __reduce__(self):
            return operator.getitem, (
                Annotated, (self.__origin__,) + self.__metadata__
            )

        def __eq__(self, other):
            if not isinstance(other, _Annotated):
                return NotImplemented
            if self.__origin__ != other.__origin__:
                return False
            return self.__metadata__ == other.__metadata__

        def __hash__(self):
            return hash((self.__origin__, self.__metadata__))


    class Annotated:
        """Add context specific metadata to a type.

        Example: Annotated[int, runtime_check.Unsigned] indicates to the
        hypothetical runtime_check module that this type is an unsigned int.
        Every other consumer of this type can ignore this metadata and treat
        this type as int.

        The first argument to Annotated must be a valid type (and will be in
        the __origin__ field), the remaining arguments are kept as a tuple in
        the __extra__ field.

        Details:

        - It's an error to call `Annotated` with less than two arguments.
        - Nested Annotated are flattened::

            Annotated[Annotated[int, Ann1, Ann2], Ann3] == Annotated[int, Ann1, Ann2, Ann3]

        - Instantiating an annotated type is equivalent to instantiating the
        underlying type::

            Annotated[C, Ann1](5) == C(5)

        - Annotated can be used as a generic type alias::

            Optimized = Annotated[T, runtime.Optimize]
            Optimized[int] == Annotated[int, runtime.Optimize]

            OptimizedList = Annotated[List[T], runtime.Optimize]
            OptimizedList[int] == Annotated[List[int], runtime.Optimize]
        """

        __slots__ = ()

        def __new__(cls, *args, **kwargs):
            raise TypeError("Type Annotated cannot be instantiated.")

        @typing._tp_cache
        def __class_getitem__(cls, params):
            if not isinstance(params, tuple) or len(params) < 2:
                raise TypeError("Annotated[...] should be used "
                                "with at least two arguments (a type and an "
                                "annotation).")
            msg = "Annotated[t, ...]: t must be a type."
            origin = typing._type_check(params[0], msg)
            metadata = tuple(params[1:])
            return _Annotated(origin, metadata)

        def __init_subclass__(cls, *args, **kwargs):
            raise TypeError("Cannot inherit from Annotated")

    def _strip_annotations(t):
        """Strips the annotations from a given type.
        """
        if isinstance(t, _Annotated):
            return _strip_annotations(t.__origin__)
        if isinstance(t, typing._GenericAlias):
            stripped_args = tuple(_strip_annotations(a) for a in t.__args__)
            if stripped_args == t.__args__:
                return t
            res = t.copy_with(stripped_args)
            res._special = t._special
            return res
        return t

    def get_type_hints(obj, globalns=None, localns=None, include_extras=False):
        """Return type hints for an object.

        This is often the same as obj.__annotations__, but it handles
        forward references encoded as string literals, adds Optional[t] if a
        default value equal to None is set and recursively replaces all
        'Annotated[T, ...]' with 'T' (unless 'include_extras=True').

        The argument may be a module, class, method, or function. The annotations
        are returned as a dictionary. For classes, annotations include also
        inherited members.

        TypeError is raised if the argument is not of a type that can contain
        annotations, and an empty dictionary is returned if no annotations are
        present.

        BEWARE -- the behavior of globalns and localns is counterintuitive
        (unless you are familiar with how eval() and exec() work).  The
        search order is locals first, then globals.

        - If no dict arguments are passed, an attempt is made to use the
          globals from obj (or the respective module's globals for classes),
          and these are also used as the locals.  If the object does not appear
          to have globals, an empty dictionary is used.

        - If one dict argument is passed, it is used for both globals and
          locals.

        - If two dict arguments are passed, they specify globals and
          locals, respectively.
        """
        hint = typing.get_type_hints(obj, globalns=globalns, localns=localns)
        if include_extras:
            return hint
        return {k: _strip_annotations(t) for k, t in hint.items()}
