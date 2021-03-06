# Copyright 2018 The Cirq Developers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The circuit data structure.

Circuits consist of a list of Moments, each Moment made up of a set of
Operations. Each Operation is a Gate that acts on some Qubits, for a given
Moment the Operations must all act on distinct Qubits.
"""

from collections import defaultdict

from typing import (
    List, Any, Dict, FrozenSet, Callable, Iterable, Iterator, Optional,
    Sequence, Union, Type, Tuple, cast, TypeVar, overload
)

import numpy as np
import math

import cirq
from cirq import devices, ops, extension, study, linalg, protocols
from cirq.circuits.insert_strategy import InsertStrategy
from cirq.circuits.moment import Moment
from cirq.circuits.text_diagram_drawer import TextDiagramDrawer
from cirq.circuits.qasm_output import QasmOutput

T_DESIRED_GATE_TYPE = TypeVar('T_DESIRED_GATE_TYPE', bound='ops.Gate')


class Circuit(ops.ParameterizableEffect):
    """A mutable list of groups of operations to apply to some qubits.

    Methods returning information about the circuit:
        next_moment_operating_on
        prev_moment_operating_on
        operation_at
        qubits
        findall_operations
        to_unitary_matrix
        apply_unitary_effect_to_state
        to_text_diagram
        to_text_diagram_drawer

    Methods for mutation:
        insert
        append
        insert_into_range
        clear_operations_touching

    Circuits can also be iterated over,
        for moment in circuit:
            ...
    and sliced,
        circuit[1:3] is a new Circuit made up of two moments, the first being
            circuit[1] and the second being circuit[2];
    and concatenated,
        circuit1 + circuit2 is a new Circuit made up of the moments in circuit1
            followed by the moments in circuit2;
    and multiplied by an integer,
        circuit * k is a new Circuit made up of the moments in circuit repeated
            k times.
    and mutated,
        circuit[1:7] = [Moment(...)]
    """

    def __init__(self,
                 moments: Iterable[Moment] = (),
                 device: devices.Device = devices.UnconstrainedDevice) -> None:
        """Initializes a circuit.

        Args:
            moments: The initial list of moments defining the circuit.
            device: Hardware that the circuit should be able to run on.
        """
        self._moments = list(moments)
        self._device = device
        self._device.validate_circuit(self)

    @property
    def device(self) -> devices.Device:
        return self._device

    @device.setter
    def device(self, new_device: devices.Device) -> None:
        new_device.validate_circuit(self)
        self._device = new_device

    @staticmethod
    def from_ops(*operations: ops.OP_TREE,
                 strategy: InsertStrategy = InsertStrategy.NEW_THEN_INLINE,
                 device: devices.Device = devices.UnconstrainedDevice
                 ) -> 'Circuit':
        """Creates an empty circuit and appends the given operations.

        Args:
            operations: The operations to append to the new circuit.
            strategy: How to append the operations.
            device: Hardware that the circuit should be able to run on.

        Returns:
            The constructed circuit containing the operations.
        """
        result = Circuit(device=device)
        result.append(operations, strategy)
        return result

    def __copy__(self) -> 'Circuit':
        return self.copy()

    def __deepcopy__(self) -> 'Circuit':
        return self.copy()

    def copy(self) -> 'Circuit':
        return Circuit(self._moments, self._device)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return self._moments == other._moments and self._device == other._device

    def __ne__(self, other):
        return not self == other

    def __len__(self):
        return len(self._moments)

    def __iter__(self):
        return iter(self._moments)

    # pylint: disable=function-redefined
    @overload
    def __getitem__(self, key: slice) -> 'Circuit':
        pass

    @overload
    def __getitem__(self, key: int) -> Moment:
        pass

    def __getitem__(self, key):
        if isinstance(key, slice):
            return Circuit(self._moments[key])
        if isinstance(key, int):
            return self._moments[key]
        else:
            raise TypeError(
                '__getitem__ called with key not of type slice or int.')

    @overload
    def __setitem__(self, key: int, value: Moment):
        pass

    @overload
    def __setitem__(self, key: slice, value: Iterable[Moment]):
        pass

    def __setitem__(self, key, value):
        if isinstance(key, int):
            if not isinstance(value, Moment):
                raise TypeError('Can only assign Moments into Circuits.')
            self._device.validate_moment(value)

        if isinstance(key, slice):
            value = list(value)
            if any(not isinstance(v, Moment) for v in value):
                raise TypeError('Can only assign Moments into Circuits.')
            for moment in value:
                self._device.validate_moment(moment)

        self._moments[key] = value
    # pylint: enable=function-redefined

    def __delitem__(self, key: Union[int, slice]):
        del self._moments[key]

    def __iadd__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        if (other.device != self._device and
                other.device != devices.UnconstrainedDevice):
            raise ValueError("Other circuit's device is not compatible.")
        for moment in other:
            self._device.validate_moment(moment)
        self._moments += other._moments
        return self

    def __add__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        device = (self._device
                    if other.device is devices.UnconstrainedDevice
                    else other.device)
        device_2 = (other.device
                    if self._device is devices.UnconstrainedDevice
                    else self._device)
        if device != device_2:
            raise ValueError("Can't add circuits with incompatible devices.")

        for moment in self:
            device.validate_moment(moment)
        for moment in other:
            device.validate_moment(moment)

        return Circuit(self._moments + other._moments,
                       device=device)

    def __imul__(self, repetitions: int):
        if not isinstance(repetitions, int):
            return NotImplemented
        self._moments *= repetitions
        return self

    def __mul__(self, repetitions: int):
        if not isinstance(repetitions, int):
            return NotImplemented
        return Circuit(self._moments * repetitions,
                       device=self._device)

    def __rmul__(self, repetitions: int):
        if not isinstance(repetitions, int):
            return NotImplemented
        return self * repetitions

    def __repr__(self):
        if not self._moments and self._device == devices.UnconstrainedDevice:
            return 'cirq.Circuit()'

        if not self._moments:
            return 'cirq.Circuit(device={!r})'.format(self._device)

        moment_str = _list_repr_with_indented_item_lines(self._moments)
        if self._device == devices.UnconstrainedDevice:
            return 'cirq.Circuit(moments={})'.format(moment_str)

        return 'cirq.Circuit(moments={}, device={!r})'.format(moment_str,
                                                              self._device)

    def __str__(self):
        return self.to_text_diagram()

    __hash__ = None  # type: ignore

    def with_device(
            self,
            new_device: devices.Device,
            qubit_mapping: Callable[[ops.QubitId], ops.QubitId] = lambda e: e,
            ) -> 'Circuit':
        """Maps the current circuit onto a new device, and validates.

        Args:
            new_device: The new device that the circuit should be on.
            qubit_mapping: How to translate qubits from the old device into
                qubits on the new device.

        Returns:
            The translated circuit.
        """
        return Circuit(
            moments=[Moment(operation.transform_qubits(qubit_mapping)
                            for operation in moment.operations)
                     for moment in self._moments],
            device=new_device
        )

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Print ASCII diagram in Jupyter."""
        if cycle:
            # There should never be a cycle.  This is just in case.
            p.text('Circuit(...)')
        else:
            p.text(self.to_text_diagram())

    def _repr_html_(self) -> str:
        """Print ASCII diagram in Jupyter notebook without wrapping lines."""
        return ('<pre style="overflow: auto; white-space: pre;">'
                + self.to_text_diagram()
                + '</pre>')

    def _first_moment_operating_on(self,
                                   qubits: Iterable[ops.QubitId],
                                   indices: Iterable[int]) -> Optional[int]:
        qubits = frozenset(qubits)
        for m in indices:
            if self._has_op_at(m, qubits):
                return m
        return None

    def next_moment_operating_on(self,
                                 qubits: Iterable[ops.QubitId],
                                 start_moment_index: int = 0,
                                 max_distance: int = None) -> Optional[int]:
        """Finds the index of the next moment that touches the given qubits.

        Args:
            qubits: We're looking for operations affecting any of these qubits.
            start_moment_index: The starting point of the search.
            max_distance: The number of moments (starting from the start index
                and moving forward) to check. Defaults to no limit.

        Returns:
            None if there is no matching moment, otherwise the index of the
            earliest matching moment.

        Raises:
          ValueError: negative max_distance.
        """
        max_circuit_distance = len(self._moments) - start_moment_index
        if max_distance is None:
            max_distance = max_circuit_distance
        elif max_distance < 0:
            raise ValueError('Negative max_distance: {}'.format(max_distance))
        else:
            max_distance = min(max_distance, max_circuit_distance)

        return self._first_moment_operating_on(
            qubits,
            range(start_moment_index, start_moment_index + max_distance))

    def next_moments_operating_on(self,
                                 qubits: Iterable[ops.QubitId],
                                 start_moment_index: int = 0
                                 ) -> Dict[ops.QubitId, int]:
        """Finds the index of the next moment that touches each qubit.

        Args:
            qubits: The qubits to find the next moments acting on.
            start_moment_index: The starting point of the search.

        Returns:
            The index of the next moment that touches each qubit. If there
            is no such moment, the next moment is specified as the number of
            moments in the circuit. Equivalently, can be characterized as one
            plus the index of the last moment after start_moment_index
            (inclusive) that does *not* act on a given qubit.
        """
        next_moments = {}
        for q in qubits:
            next_moment = self.next_moment_operating_on([q], start_moment_index)
            next_moments[q] = (len(self._moments) if next_moment is None else
                               next_moment)
        return next_moments

    def prev_moment_operating_on(
            self,
            qubits: Sequence[ops.QubitId],
            end_moment_index: Optional[int] = None,
            max_distance: Optional[int] = None) -> Optional[int]:
        """Finds the index of the next moment that touches the given qubits.

        Args:
            qubits: We're looking for operations affecting any of these qubits.
            end_moment_index: The moment index just after the starting point of
                the reverse search. Defaults to the length of the list of
                moments.
            max_distance: The number of moments (starting just before from the
                end index and moving backward) to check. Defaults to no limit.

        Returns:
            None if there is no matching moment, otherwise the index of the
            latest matching moment.

        Raises:
            ValueError: negative max_distance.
        """
        if end_moment_index is None:
            end_moment_index = len(self._moments)

        if max_distance is None:
            max_distance = len(self._moments)
        elif max_distance < 0:
            raise ValueError('Negative max_distance: {}'.format(max_distance))
        else:
            max_distance = min(end_moment_index, max_distance)

        # Don't bother searching indices past the end of the list.
        if end_moment_index > len(self._moments):
            d = end_moment_index - len(self._moments)
            end_moment_index -= d
            max_distance -= d
        if max_distance <= 0:
            return None

        return self._first_moment_operating_on(qubits,
                                               (end_moment_index - k - 1
                                                for k in range(max_distance)))

    def _prev_moment_available(
            self,
            op: ops.Operation,
            end_moment_index: int) -> Optional[int]:
        last_available = end_moment_index
        k = end_moment_index
        while k > 0:
            k -= 1
            if not self._can_commute_past(k, op):
                return last_available
            if self._can_add_op_at(k, op):
                last_available = k
        return last_available

    def operation_at(self,
                     qubit: ops.QubitId,
                     moment_index: int) -> Optional[ops.Operation]:
        """Finds the operation on a qubit within a moment, if any.

        Args:
            qubit: The qubit to check for an operation on.
            moment_index: The index of the moment to check for an operation
                within. Allowed to be beyond the end of the circuit.

        Returns:
            None if there is no operation on the qubit at the given moment, or
            else the operation.
        """
        if not 0 <= moment_index < len(self._moments):
            return None
        for op in self._moments[moment_index].operations:
            if qubit in op.qubits:
                return op
        return None

    def findall_operations(self, predicate: Callable[[ops.Operation], bool]
                           ) -> Iterable[Tuple[int, ops.Operation]]:
        """Find the locations of all operations that satisfy a given condition.

        This returns an iterator of (index, operation) tuples where each
        operation satisfies op_cond(operation) is truthy. The indices are
        in order of the moments and then order of the ops within that moment.

        Args:
            predicate: A method that takes an Operation and returns a Truthy
                value indicating the operation meets the find condition.

        Returns:
            An iterator (index, operation)'s that satisfy the op_condition.
        """
        for index, moment in enumerate(self._moments):
            for op in moment.operations:
                if predicate(op):
                    yield index, op

    def findall_operations_with_gate_type(
            self,
            gate_type: Type[T_DESIRED_GATE_TYPE]
            ) -> Iterable[Tuple[int,
                                ops.GateOperation,
                                T_DESIRED_GATE_TYPE]]:
        """Find the locations of all gate operations of a given type.

        Args:
            gate_type: The type of gate to find, e.g. RotXGate or
                MeasurementGate.

        Returns:
            An iterator (index, operation, gate)'s for operations with the given
            gate type.
        """
        result = self.findall_operations(
            lambda operation: (isinstance(operation, ops.GateOperation) and
                               isinstance(operation.gate, gate_type)))
        for index, op in result:
            gate_op = cast(ops.GateOperation, op)
            yield index, gate_op, cast(T_DESIRED_GATE_TYPE, gate_op.gate)

    def are_all_measurements_terminal(self):
        return all(
            self.next_moment_operating_on(op.qubits, i + 1) is None for (i, op)
            in self.findall_operations(ops.MeasurementGate.is_measurement))

    def _pick_or_create_inserted_op_moment_index(
            self, splitter_index: int, op: ops.Operation,
            strategy: InsertStrategy) -> int:
        """Determines and prepares where an insertion will occur.

        Args:
            splitter_index: The index to insert at.
            op: The operation that will be inserted.
            strategy: The insertion strategy.

        Returns:
            The index of the (possibly new) moment where the insertion should
                occur.

        Raises:
            ValueError: Unrecognized append strategy.
        """

        if (strategy is InsertStrategy.NEW or
                strategy is InsertStrategy.NEW_THEN_INLINE):
            self._moments.insert(splitter_index, Moment())
            return splitter_index

        if strategy is InsertStrategy.INLINE:
            if (0 <= splitter_index - 1 < len(self._moments) and
                    self._can_add_op_at(splitter_index - 1, op)):
                return splitter_index - 1

            return self._pick_or_create_inserted_op_moment_index(
                splitter_index, op, InsertStrategy.NEW)

        if strategy is InsertStrategy.EARLIEST:
            if self._can_add_op_at(splitter_index, op):
                p = self._prev_moment_available(op, splitter_index)
                return p or 0

            return self._pick_or_create_inserted_op_moment_index(
                splitter_index, op, InsertStrategy.INLINE)

        raise ValueError('Unrecognized append strategy: {}'.format(strategy))

    def _has_op_at(self,
                   moment_index: int,
                   qubits: Iterable[ops.QubitId]) -> bool:
        return (0 <= moment_index < len(self._moments) and
                self._moments[moment_index].operates_on(qubits))

    def _can_add_op_at(self,
                       moment_index: int,
                       operation: ops.Operation) -> bool:
        if not 0 <= moment_index < len(self._moments):
            return True
        return self._device.can_add_operation_into_moment(
            operation,
            self._moments[moment_index])

    def _can_commute_past(self,
                          moment_index: int,
                          operation: ops.Operation) -> bool:
        return not self._moments[moment_index].operates_on(operation.qubits)

    def insert(
            self,
            index: int,
            moment_or_operation_tree: Union[Moment, ops.OP_TREE],
            strategy: InsertStrategy = InsertStrategy.NEW_THEN_INLINE) -> int:
        """Inserts operations into the middle of the circuit.

        Args:
            index: The index to insert all of the operations at.
            moment_or_operation_tree: An operation or tree of operations.
            strategy: How to pick/create the moment to put operations into.

        Returns:
            The insertion index that will place operations just after the
            operations that were inserted by this method.

        Raises:
            IndexError: Bad insertion index.
            ValueError: Bad insertion strategy.
        """
        if isinstance(moment_or_operation_tree, Moment):
            self._device.validate_moment(moment_or_operation_tree)
            self._moments.insert(index, moment_or_operation_tree)
            return index + 1

        if not 0 <= index <= len(self._moments):
            raise IndexError('Insert index out of range: {}'.format(index))

        operations = list(ops.flatten_op_tree(ops.transform_op_tree(
            moment_or_operation_tree,
            self._device.decompose_operation)))
        for op in operations:
            self._device.validate_operation(op)

        k = index
        for op in operations:
            p = self._pick_or_create_inserted_op_moment_index(k, op, strategy)
            while p >= len(self._moments):
                self._moments.append(Moment())
            self._moments[p] = self._moments[p].with_operation(op)
            self._device.validate_moment(self._moments[p])
            k = max(k, p + 1)
            if strategy is InsertStrategy.NEW_THEN_INLINE:
                strategy = InsertStrategy.INLINE
        return k

    def insert_into_range(self,
                          operations: ops.OP_TREE,
                          start: int,
                          end: int) -> int:
        """Writes operations inline into an area of the circuit.

        Args:
            start: The start of the range (inclusive) to write the
                given operations into.
            end: The end of the range (exclusive) to write the given
                operations into. If there are still operations remaining,
                new moments are created to fit them.
            operations: An operation or tree of operations to insert.

        Returns:
            An insertion index that will place operations after the operations
            that were inserted by this method.

        Raises:
            IndexError: Bad inline_start and/or inline_end.
        """
        if not 0 <= start <= end <= len(self):
            raise IndexError('Bad insert indices: [{}, {})'.format(
                start, end))

        operations = list(ops.flatten_op_tree(operations))
        for op in operations:
            self._device.validate_operation(op)

        i = start
        op_index = 0
        while op_index < len(operations):
            op = operations[op_index]
            while i < end and not self._device.can_add_operation_into_moment(
                    op, self._moments[i]):
                i += 1
            if i >= end:
                break
            self._moments[i] = self._moments[i].with_operation(op)
            op_index += 1

        if op_index >= len(operations):
            return end

        return self.insert(end, operations[op_index:])

    @staticmethod
    def _pick_inserted_ops_moment_indices(operations: Sequence[ops.Operation],
                                          start: int=0,
                                          frontier: Dict[ops.QubitId, int]=None
                                          ) -> Tuple[Sequence[int],
                                                     Dict[ops.QubitId, int]]:
        """Greedily assigns operations to moments.

        Args:
            operations: The operations to assign to moments.
            start: The first moment to consider assignment to.
            frontier: The first moment to which an operation acting on a qubit
                can be assigned. Updated in place as operations are assigned.

        Returns:
            The frontier giving the index of the moment after the last one to
            which an operation that acts on each qubit is assigned. If a
            frontier was specified as an argument, this is the same object.
        """
        if frontier is None:
            frontier = defaultdict(lambda: 0)
        moment_indices = []
        for op in operations:
            op_start = max(start, max(frontier[q] for q in op.qubits))
            moment_indices.append(op_start)
            for q in op.qubits:
                frontier[q] = max(frontier[q], op_start + 1)

        return moment_indices, frontier


    def _push_frontier(self,
                      early_frontier: Dict[ops.QubitId, int],
                      late_frontier: Dict[ops.QubitId, int],
                      update_qubits: Iterable[ops.QubitId]=None
                      ) -> Tuple[int, int]:
        """Inserts moments to separate two frontiers.

        After insertion n_new moments, the following holds:
           for q in late_frontier:
               early_frontier[q] <= late_frontier[q] + n_new
           for q in update_qubits:
               early_frontier[q] the identifies the same moment as before
                   (but whose index may have changed if this moment is after
                   those inserted).

        Args:
            early_frontier: The earlier frontier. For qubits not in the later
                frontier, this is updated to account for the newly inserted
                moments.
            late_frontier: The later frontier. This is not modified.
            update_qubits: The qubits for which to update early_frontier to
                account for the newly inserted moments.

        Returns:
            (index at which new moments were inserted, how many new moments
            were inserted) if new moments were indeed inserted. (0, 0)
            otherwise.
        """
        if update_qubits is None:
            update_qubits = set(early_frontier).difference(late_frontier)
        n_new_moments = (max(early_frontier.get(q, 0) - late_frontier[q]
                             for q in late_frontier)
                         if late_frontier else 0)
        if n_new_moments > 0:
            insert_index = min(late_frontier.values())
            self._moments[insert_index:insert_index] = (
                    [Moment()] * n_new_moments)
            for q in update_qubits:
                if early_frontier.get(q, 0) > insert_index:
                    early_frontier[q] += n_new_moments
            return insert_index, n_new_moments
        return (0, 0)

    def _insert_operations(self,
                          operations: Sequence[ops.Operation],
                          insertion_indices: Sequence[int]) -> None:
        """Inserts operations at the specified moments. Appends new moments if
        necessary.

        Args:
            operations: The operations to insert.
            insertion_indices: Where to insert them, i.e. operations[i] is
                inserted into moments[insertion_indices[i].

        Raises:
            ValueError: operations and insert_indices have different lengths.

        NB: It's on the caller to ensure that the operations won't conflict
        with operations already in the moment or even each other.
        """
        if len(operations) != len(insertion_indices):
            raise ValueError('operations and insertion_indices must have the'
                             'same length.')
        self._moments += [Moment() for _ in range(1 + max(insertion_indices) -
                                                  len(self))]
        moment_to_ops = defaultdict(list) # type: Dict[int, List[ops.Operation]]
        for op_index, moment_index in enumerate(insertion_indices):
            moment_to_ops[moment_index].append(operations[op_index])
        for moment_index, new_ops in moment_to_ops.items():
            self._moments[moment_index] = Moment(
                    self._moments[moment_index].operations + tuple(new_ops))


    def insert_at_frontier(self,
                           operations: ops.OP_TREE,
                           start: int,
                           frontier: Dict[ops.QubitId, int]=None
                           ) -> Dict[ops.QubitId, int]:
        """Inserts operations inline at frontier.

        Args:
            operations: the operations to insert
            start: the moment at which to start inserting the operations
            frontier: frontier[q] is the earliest moment in which an operation
                acting on qubit q can be placed.
        """
        if frontier is None:
            frontier = defaultdict(lambda: 0)
        operations = tuple(ops.flatten_op_tree(operations))
        if not operations:
            return frontier
        qubits = set(q for op in operations for q in op.qubits)
        if any(frontier[q] > start for q in qubits):
            raise ValueError('The frontier for qubits on which the operations'
                             'to insert act cannot be after start.')

        next_moments = self.next_moments_operating_on(qubits, start)

        insertion_indices, _ = self._pick_inserted_ops_moment_indices(
                operations, start, frontier)

        self._push_frontier(frontier, next_moments)

        self._insert_operations(operations, insertion_indices)

        return frontier


    def batch_remove(self,
                     removals: Iterable[Tuple[int, ops.Operation]]) -> None:
        """Removes several operations from a circuit.

        Args:
            removals: A sequence of (moment_index, operation) tuples indicating
                operations to delete from the moments that are present. All
                listed operations must actually be present or the edit will
                fail (without making any changes to the circuit).

        ValueError:
            One of the operations to delete wasn't present to start with.

        IndexError:
            Deleted from a moment that doesn't exist.
        """
        copy = self.copy()
        for i, op in removals:
            if op not in copy._moments[i].operations:
                raise ValueError(
                    "Can't remove {} @ {} because it doesn't exist.".format(
                        op, i))
            copy._moments[i] = Moment(old_op
                                      for old_op in copy._moments[i].operations
                                      if op != old_op)
        self._device.validate_circuit(copy)
        self._moments = copy._moments

    def batch_insert_into(self,
                          insert_intos: Iterable[Tuple[int, ops.Operation]]
                          ) -> None:
        """Inserts operations into empty spaces in existing moments.

        If any of the insertions fails (due to colliding with an existing
        operation), this method fails without making any changes to the circuit.

        Args:
            insert_intos: A sequence of (moment_index, new_operation)
                pairs indicating a moment to add a new operation into.

        ValueError:
            One of the insertions collided with an existing operation.

        IndexError:
            Inserted into a moment index that doesn't exist.
        """
        copy = self.copy()
        for i, op in insert_intos:
            copy._moments[i] = copy._moments[i].with_operation(op)
        self._device.validate_circuit(copy)
        self._moments = copy._moments

    def batch_insert(self,
                     insertions: Iterable[Tuple[int, ops.OP_TREE]]) -> None:
        """Applies a batched insert operation to the circuit.

        Transparently handles the fact that earlier insertions may shift
        the index that later insertions should occur at. For example, if you
        insert an operation at index 2 and at index 4, but the insert at index 2
        causes a new moment to be created, then the insert at "4" will actually
        occur at index 5 to account for the shift from the new moment.

        All insertions are done with the strategy 'EARLIEST'.

        Args:
            insertions: A sequence of (insert_index, operations) pairs
                indicating operations to add into the circuit at specific
                places.
        """
        # Work on a copy in case validation fails halfway through.
        copy = self.copy()
        shift = 0
        for i, tree in sorted(insertions, key=lambda e: e[0]):
            for op in ops.flatten_op_tree(tree):
                next_index = copy.insert(i + shift, op, InsertStrategy.EARLIEST)
                if next_index > i:
                    shift += 1
        self._moments = copy._moments

    def append(
            self,
            moment_or_operation_tree: Union[Moment, ops.OP_TREE],
            strategy: InsertStrategy = InsertStrategy.NEW_THEN_INLINE):
        """Appends operations onto the end of the circuit.

        Args:
            moment_or_operation_tree: An operation or tree of operations.
            strategy: How to pick/create the moment to put operations into.
        """
        self.insert(len(self._moments), moment_or_operation_tree, strategy)

    def clear_operations_touching(self,
                                  qubits: Iterable[ops.QubitId],
                                  moment_indices: Iterable[int]):
        """Clears operations that are touching given qubits at given moments.

        Args:
            qubits: The qubits to check for operations on.
            moment_indices: The indices of moments to check for operations
                within.
        """
        qubits = frozenset(qubits)
        for k in moment_indices:
            if 0 <= k < len(self._moments):
                self._moments[k] = self._moments[k].without_operations_touching(
                    qubits)

    def all_qubits(self) -> FrozenSet[ops.QubitId]:
        """Returns the qubits acted upon by Operations in this circuit."""
        return frozenset(q for m in self._moments for q in m.qubits)

    def all_operations(self) -> Iterator[ops.Operation]:
        """Iterates over the operations applied by this circuit.

        Operations from earlier moments will be iterated over first. Operations
        within a moment are iterated in the order they were given to the
        moment's constructor.
        """
        return (op for moment in self for op in moment.operations)

    def _unitary_(self) -> Union[np.ndarray, type(NotImplemented)]:
        """Converts the circuit into a unitary matrix, if possible.

        If the circuit contains any non-terminal measurements, the conversion
        into a unitary matrix fails (i.e. returns NotImplemented). Terminal
        measurements are ignored when computing the unitary matrix. The unitary
        matrix is the product of the unitary matrix of all operations in the
        circuit (after expanding them to apply to the whole system).
        """
        if not self.are_all_measurements_terminal():
            return NotImplemented
        return self.to_unitary_matrix(ignore_terminal_measurements=True)

    def to_unitary_matrix(
            self,
            qubit_order: ops.QubitOrderOrList = ops.QubitOrder.DEFAULT,
            qubits_that_should_be_present: Iterable[ops.QubitId] = (),
            ignore_terminal_measurements: bool = True,
            ext: extension.Extensions = None,
            dtype: np.dtype = np.complex128) -> np.ndarray:
        """Converts the circuit into a unitary matrix, if possible.

        Args:
            qubit_order: Determines how qubits are ordered when passing matrices
                into np.kron.
            ext: The extensions to use when attempting to cast operations into
                CompositeOperation instances.
            qubits_that_should_be_present: Qubits that may or may not appear
                in operations within the circuit, but that should be included
                regardless when generating the matrix.
            ignore_terminal_measurements: When set, measurements at the end of
                the circuit are ignored instead of causing the method to
                fail.
            dtype: The numpy dtype for the returned unitary. Must be a complex
                dtype.

        Returns:
            A (possibly gigantic) 2d numpy array corresponding to a matrix
            equivalent to the circuit's effect on a quantum state.

        Raises:
            ValueError: The circuit contains measurement gates that are not
                ignored.
            TypeError: The circuit contains gates that don't have a known
                unitary matrix, e.g. gates parameterized by a Symbol.
        """

        if ext is None:
            ext = extension.Extensions()

        if not ignore_terminal_measurements and any(
                ops.MeasurementGate.is_measurement(op)
                for op in self.all_operations()):
            raise ValueError('Circuit contains a measurement.')

        if not self.are_all_measurements_terminal():
            raise ValueError('Circuit contains a non-terminal measurement.')

        qs = ops.QubitOrder.as_qubit_order(qubit_order).order_for(
            self.all_qubits().union(qubits_that_should_be_present))
        n = len(qs)

        state = np.eye(1 << n, dtype=np.complex128)
        state.shape = (2,) * (2 * n)

        result = _apply_unitary_circuit(self, state, qs, ext, dtype)
        return result.reshape((1 << n, 1 << n))

    def apply_unitary_effect_to_state(
            self,
            initial_state: Union[int, np.ndarray] = 0,
            qubit_order: ops.QubitOrderOrList = ops.QubitOrder.DEFAULT,
            qubits_that_should_be_present: Iterable[ops.QubitId] = (),
            ignore_terminal_measurements: bool = True,
            ext: extension.Extensions = None,
            dtype: np.dtype = np.complex128,
            noise_model = None) -> np.ndarray:
        """Left-multiplies a state vector by the circuit's unitary effect.

        A circuit's "unitary effect" is the unitary matrix produced by
        multiplying together all of its gates' unitary matrices. A circuit
        with non-unitary gates (such as measurement or parameterized gates) does
        not have a well-defined unitary effect, and the method will fail if such
        operations are present.

        For convenience, terminal measurements are automatically ignored
        instead of causing a failure. Set the 'ignore_terminal_measurements'
        argument to False to disable this behavior.

        This method is equivalent to left-multiplying the input state by
        circuit.to_unitary_matrix(...), but computed in a more efficient way.

        Args:
            qubit_order: Determines how qubits are ordered when passing matrices
                into np.kron.
            initial_state: The input state for the circuit. This can be an int
                or a vector. When this is an int, it refers to a computational
                basis state (e.g. 5 means initialize to |5> = |...000101>). If
                this is a state vector, it directly specifies the initial
                state's amplitudes. The vector must be a flat numpy array with a
                type that can be converted to np.complex128.
            qubits_that_should_be_present: Qubits that may or may not appear
                in operations within the circuit, but that should be included
                regardless when generating the matrix.
            ignore_terminal_measurements: When set, measurements at the end of
                the circuit are ignored instead of causing the method to
                fail.
            ext: The extensions to use when attempting to cast operations into
                KnownMatrix instances.
            dtype: The numpy dtype for the returned unitary. Must be a complex
                dtype.

        Returns:
            A (possibly gigantic) numpy array storing the superposition that
            came out of the circuit for the given input state.

        Raises:
            ValueError: The circuit contains measurement gates that are not
                ignored.
            TypeError: The circuit contains gates that don't have a known
                unitary matrix, e.g. gates parameterized by a Symbol.
        """

        if ext is None:
            ext = extension.Extensions()

        if not ignore_terminal_measurements and any(
                ops.MeasurementGate.is_measurement(op)
                for op in self.all_operations()):
            raise ValueError('Circuit contains a measurement.')

        if not self.are_all_measurements_terminal():
            raise ValueError('Circuit contains a non-terminal measurement.')

        qs = ops.QubitOrder.as_qubit_order(qubit_order).order_for(
            self.all_qubits().union(qubits_that_should_be_present))
        n = len(qs)

        if isinstance(initial_state, int):
            state = np.zeros(cirq.QUDIT_LEVELS ** n, dtype=dtype)
            state[initial_state] = 1
        else:
            state = initial_state.astype(dtype)

        target_output_state = np.copy(state)
        tmp = target_output_state[int((n - 1) * '1' + '0', cirq.QUDIT_LEVELS)]
        target_output_state[int((n - 1) * '1' + '0', cirq.QUDIT_LEVELS)] = target_output_state[int((n - 1) * '1' + '1', cirq.QUDIT_LEVELS)]
        target_output_state[int((n - 1) * '1' + '1', cirq.QUDIT_LEVELS)] = tmp

        state.shape = (cirq.QUDIT_LEVELS,) * n

        result = _apply_unitary_circuit(self, state, qs, ext, dtype, noise_model=noise_model)
        result = result.reshape((cirq.QUDIT_LEVELS ** n,))

        # return fidelity between result and target_output_state
        return np.linalg.norm(np.vdot(result, target_output_state)) ** 2, result

    def to_text_diagram(
            self,
            ext: extension.Extensions = None,
            use_unicode_characters: bool = True,
            transpose: bool = False,
            precision: Optional[int] = 3,
            qubit_order: ops.QubitOrderOrList = ops.QubitOrder.DEFAULT) -> str:
        """Returns text containing a diagram describing the circuit.

        Args:
            ext: For extending operations/gates to implement TextDiagrammable.
            use_unicode_characters: Determines if unicode characters are
                allowed (as opposed to ascii-only diagrams).
            transpose: Arranges qubit wires vertically instead of horizontally.
            precision: Number of digits to display in text diagram
            qubit_order: Determines how qubits are ordered in the diagram.

        Returns:
            The text diagram.
        """
        diagram = self.to_text_diagram_drawer(
            ext=ext,
            use_unicode_characters=use_unicode_characters,
            qubit_name_suffix='' if transpose else ': ',
            precision=precision,
            qubit_order=qubit_order,
            transpose=transpose)

        return diagram.render(
            crossing_char=(None
                           if use_unicode_characters
                           else ('-' if transpose else '|')),
            horizontal_spacing=1 if transpose else 3,
            use_unicode_characters=use_unicode_characters)

    def to_text_diagram_drawer(
            self,
            ext: extension.Extensions = None,
            use_unicode_characters: bool = True,
            qubit_name_suffix: str = '',
            transpose: bool = False,
            precision: Optional[int] = 3,
            qubit_order: ops.QubitOrderOrList = ops.QubitOrder.DEFAULT,
    ) -> TextDiagramDrawer:
        """Returns a TextDiagramDrawer with the circuit drawn into it.

        Args:
            ext: For extending operations/gates to implement TextDiagrammable.
            use_unicode_characters: Determines if unicode characters are
                allowed (as opposed to ascii-only diagrams).
            qubit_name_suffix: Appended to qubit names in the diagram.
            transpose: Arranges qubit wires vertically instead of horizontally.
            precision: Number of digits to use when representing numbers.
            qubit_order: Determines how qubits are ordered in the diagram.

        Returns:
            The TextDiagramDrawer instance.
        """
        if ext is None:
            ext = extension.Extensions()

        qubits = ops.QubitOrder.as_qubit_order(qubit_order).order_for(
            self.all_qubits())
        qubit_map = {qubits[i]: i for i in range(len(qubits))}

        diagram = TextDiagramDrawer()
        for q, i in qubit_map.items():
            diagram.write(0, i, str(q) + qubit_name_suffix)

        for moment in self._moments:
            _draw_moment_in_diagram(moment,
                                    ext,
                                    use_unicode_characters,
                                    qubit_map,
                                    diagram,
                                    precision)

        w = diagram.width()
        for i in qubit_map.values():
            diagram.horizontal_line(i, 0, w)

        if transpose:
            diagram = diagram.transpose()

        return diagram

    def is_parameterized(self,
                         ext: extension.Extensions = None) -> bool:
        if ext is None:
            ext = extension.Extensions()
        return any(cast(ops.ParameterizableEffect, op).is_parameterized()
                   for op in self.all_operations()
                   if ext.try_cast(ops.ParameterizableEffect, op) is not None)

    def with_parameters_resolved_by(self,
                                    param_resolver: study.ParamResolver,
                                    ext: extension.Extensions = None
                                    ) -> 'Circuit':
        if ext is None:
            ext = extension.Extensions()
        resolved_circuit = Circuit()
        for moment in self:
            resolved_circuit.append(_resolve_operations(
                moment.operations,
                param_resolver,
                ext))
        return resolved_circuit

    def to_qasm(self,
                header: str = 'Generated from Cirq',
                precision: int = 10,
                qubit_order: ops.QubitOrderOrList = ops.QubitOrder.DEFAULT,
                ext: extension.Extensions = None
                ) -> str:
        """Returns QASM equivalent to the circuit.

        Args:
            header: A multi-line string that is placed in a comment at the top
                of the QASM.
            precision: Number of digits to use when representing numbers.
            qubit_order: Determines how qubits are ordered in the QASM
                register.
            ext: For extending operations/gates to implement
                QasmConvertibleOperation/QasmConvertibleGate.
        """
        qubits = ops.QubitOrder.as_qubit_order(qubit_order).order_for(
            self.all_qubits())
        output = QasmOutput(operations=self.all_operations(),
                            qubits=qubits,
                            header=header,
                            precision=precision,
                            version='2.0',
                            ext=ext)
        return str(output)

    def save_qasm(self,
                  file_path: Union[str, bytes, int],
                  header: str = 'Generated from Cirq',
                  precision: int = 10,
                  qubit_order: ops.QubitOrderOrList = ops.QubitOrder.DEFAULT,
                  ext: extension.Extensions = None
                  ) -> None:
        """Save a QASM file equivalent to the circuit.

        Args:
            header: A multi-line string that is placed in a comment at the top
                of the QASM.
            precision: Number of digits to use when representing numbers.
            qubit_order: Determines how qubits are ordered in the QASM
                register.
            ext: For extending operations/gates to implement
                QasmConvertibleOperation/QasmConvertibleGate.
        """
        qubits = ops.QubitOrder.as_qubit_order(qubit_order).order_for(
            self.all_qubits())
        output = QasmOutput(operations=self.all_operations(),
                            qubits=qubits,
                            header=header,
                            precision=precision,
                            version='2.0',
                            ext=ext)
        output.save(file_path)


def _resolve_operations(
        operations: Iterable[ops.Operation],
        param_resolver: study.ParamResolver,
        ext: extension.Extensions) -> List[ops.Operation]:
    resolved_operations = []  # type: List[ops.Operation]
    for op in operations:
        cast_op = ext.try_cast(ops.ParameterizableEffect, op)
        if cast_op is None:
            resolved_op = op
        else:
            resolved_op = cast(
                    ops.Operation,
                    cast_op.with_parameters_resolved_by(param_resolver))
        resolved_operations.append(resolved_op)
    return resolved_operations


def _get_operation_text_diagram_info_with_fallback(
        op: ops.Operation,
        args: ops.TextDiagramInfoArgs,
        ext: extension.Extensions) -> ops.TextDiagramInfo:
    text_diagrammable_op = ext.try_cast(ops.TextDiagrammable, op)
    if text_diagrammable_op is not None:
        info = text_diagrammable_op.text_diagram_info(args)
        if len(op.qubits) != len(info.wire_symbols):
            raise ValueError(
                'Wanted diagram info from {!r} for {} '
                'qubits but got {!r}'.format(
                    op,
                    len(info.wire_symbols),
                    info))
        return info

    # Fallback to a default representation using the operation's __str__.
    name = str(op)

    # Representation usually looks like 'gate(qubit1, qubit2, etc)'.
    # Try to cut off the qubit part, since that would be redundant information.
    redundant_tail = '({})'.format(', '.join(str(e) for e in op.qubits))
    if name.endswith(redundant_tail):
        name = name[:-len(redundant_tail)]

    # Include ordering in the qubit labels.
    if len(op.qubits) != 1:
        symbols = tuple('{}:{}'.format(name, i)
                        for i in range(len(op.qubits)))
    else:
        symbols = (name,)

    return ops.TextDiagramInfo(wire_symbols=symbols)


def _formatted_exponent(info: ops.TextDiagramInfo,
                        args: ops.TextDiagramInfoArgs) -> Optional[str]:
    # 1 is not shown.
    if info.exponent == 1:
        return None

    # Round -1.0 into -1.
    if info.exponent == -1:
        return '-1'

    # If it's a float, show the desired precision.
    if isinstance(info.exponent, float):
        if args.precision is not None:
            return '{{:.{}}}'.format(args.precision).format(info.exponent)
        return repr(info.exponent)

    # If the exponent is any other object, use its string representation.
    s = str(info.exponent)
    if '+' in s or ' ' in s or '-' in s[1:]:
        # The string has confusing characters. Put parens around it.
        return '({})'.format(info.exponent)
    return s


def _draw_moment_in_diagram(moment: Moment,
                            ext: extension.Extensions,
                            use_unicode_characters: bool,
                            qubit_map: Dict[ops.QubitId, int],
                            out_diagram: TextDiagramDrawer,
                            precision: Optional[int]):
    x0 = out_diagram.width()
    for op in moment.operations:
        indices = [qubit_map[q] for q in op.qubits]
        y1 = min(indices)
        y2 = max(indices)

        # Find an available column.
        x = x0
        while any(out_diagram.content_present(x, y)
                  for y in range(y1, y2 + 1)):
            x += 1

        args = ops.TextDiagramInfoArgs(
            known_qubits=op.qubits,
            known_qubit_count=len(op.qubits),
            use_unicode_characters=use_unicode_characters,
            qubit_map=qubit_map,
            precision=precision)
        info = _get_operation_text_diagram_info_with_fallback(op, args, ext)

        # Draw vertical line linking the gate's qubits.
        if y2 > y1 and info.connected:
            out_diagram.vertical_line(x, y1, y2)

        # Print gate qubit labels.
        for s, q in zip(info.wire_symbols, op.qubits):
            out_diagram.write(x, qubit_map[q], s)

        # Add an exponent to the last label.
        exponent = _formatted_exponent(info, args)
        if exponent is not None:
            out_diagram.write(x, y2, '^' + exponent)


def _apply_unitary_circuit(circuit: Circuit,
                           state: np.ndarray,
                           qubits: Tuple[ops.QubitId, ...],
                           ext: extension.Extensions,
                           dtype: np.dtype,
                           noise_model = None) -> np.ndarray:
    """Applies a circuit's unitary effect to the given vector or matrix.

    This method assumes that the caller wants to ignore measurements.

    Args:
        circuit: The circuit to simulate. All operations must have a known
            matrix or decompositions leading to known matrices. Measurements
            are allowed to be in the circuit, but they will be ignored.
        state: The initial state tensor (i.e. superposition or unitary matrix).
            This is what will be left-multiplied by the circuit's effective
            unitary. If this is a state vector, it must have shape
            (2,) * num_qubits. If it is a unitary matrix it should have shape
            (2,) * (2*num_qubits).
        qubits: The qubits in the state tensor. Determines which axes operations
            apply to. An operation targeting the k'th qubit in this list will
            operate on the k'th axis of the state tensor.
        ext: Extensions used when attempting to get matrices and decompositions
            of the operations.
        dtype: The numpy dtype to use for applying the unitary. Must be a
            complex dtype.

    Returns:
        The left-multiplied state tensor.
    """
    assert noise_model is not None
    qubit_map = {q: i for i, q in enumerate(qubits)}
    buffer = np.zeros(state.shape, dtype=dtype)
    mat_and_qs_list = list(_extract_unitaries(circuit.all_operations(), ext))
    moments = reconstruct_moments(mat_and_qs_list)
    for moment in moments:
        for mat, qs in moment:
            matrix = mat.astype(dtype).reshape((cirq.QUDIT_LEVELS,) * (2 * len(qs)))
            indices = [qubit_map[q] for q in qs]
            linalg.targeted_left_multiply(matrix, state, indices, out=buffer)
            state, buffer = buffer, state

            # Gate error:
            if matrix.size == 9:
                gate_error_matrix = noise_model.pick_single_qutrit_gate_channel()
            elif matrix.size == 81:
                gate_error_matrix = noise_model.pick_two_qutrit_gate_channel()
            else:
                assert False, "%s" % matrix.size
            gate_error_matrix = gate_error_matrix.astype(dtype).reshape((cirq.QUDIT_LEVELS,) * (2 * len(qs)))
            linalg.targeted_left_multiply(gate_error_matrix, state, indices, out=buffer)
            state, buffer = buffer, state

        # Idle Errors:
        for index in range(len(qubits)):
            if any([len(qs) == 2 for mat, qs in moment]):  # apply long idle channel
                gate_error_matrix = noise_model.pick_long_idle_channel(state, buffer, index)
            else:
                gate_error_matrix = noise_model.pick_short_idle_channel(state, buffer, index)
            gate_error_matrix = gate_error_matrix.astype(dtype).reshape((cirq.QUDIT_LEVELS,) * 2)
            linalg.targeted_left_multiply(gate_error_matrix, state, [index], out=buffer)
            buffer /= np.linalg.norm(buffer)  # idle errors may be incoherent (non-unitary) so need to renormalize
            state, buffer = buffer, state

    return state


def reconstruct_moments(mat_and_qs_list):
    mat_and_qs_list = list(mat_and_qs_list)
    moments = []
    while len(mat_and_qs_list) > 0:
        blocked_qs = set()
        moment = []
        mat_and_qs_list_next = []
        for mat, qs in mat_and_qs_list:
            if any([q in blocked_qs for q in qs]):
                blocked_qs.update(qs)  # even if we're not adding, we want to block dependent gates
                mat_and_qs_list_next.append((mat, qs))
            else:
                moment.append((mat, qs))
                blocked_qs.update(qs)
        mat_and_qs_list = mat_and_qs_list_next
        moments.append(moment)
    return moments


def _extract_unitaries(operations: Iterable[ops.Operation],
                       ext: extension.Extensions
                       ) -> Iterable[Tuple[np.ndarray,
                                           Tuple[ops.QubitId, ...]]]:
    """Yields a sequence of unitary matrices equivalent to the circuit's effect.
    """
    for op in operations:
        # Check if the operation has a known matrix.
        matrix = protocols.unitary(op, None)
        if matrix is not None:
            yield matrix, op.qubits
            continue

        # If not, check if it has a decomposition.
        composite_op = ext.try_cast(ops.CompositeOperation, op)
        if composite_op is not None:
            # Recurse decomposition to get known matrix gates.
            op_tree = composite_op.default_decompose()
            op_list = ops.flatten_op_tree(op_tree)
            for op2 in _extract_unitaries(op_list, ext):
                yield op2
            continue

        if ops.MeasurementGate.is_measurement(op):
            gate = cast(ops.MeasurementGate, cast(ops.GateOperation, op).gate)
            # Account for bit flips embedded into the measurement operation.
            for i, b in enumerate(gate.invert_mask):
                if b:
                    yield protocols.unitary(ops.X), (op.qubits[i],)

            # This is a private method called in contexts where we know
            # measurement is supposed to be skipped.
            continue

        # Otherwise, fail
        raise TypeError(
            'Operation without a known matrix or decomposition: {!r}'.format(
                op))


def _list_repr_with_indented_item_lines(items: Sequence[Any]) -> str:
    block = '\n'.join([repr(op) + ',' for op in items])
    indented = '    ' + '\n    '.join(block.split('\n'))
    return '[\n{}\n]'.format(indented)



def weighted_draw(weights):
    """Returns random index, with draw probabilities weighted by the given weights."""
    assert sum(weights) > .999 and sum(weights) < 1.001, 'sum is %s for weights: %s' % (sum(weights), weights)
    total = sum(weights)
    weights = [weight / total for weight in weights]  # normalize anyways to make sum exactly 1
    return np.random.choice(len(weights), p=weights)

class NoiseChannel(object):
    single_qutrit_kraus_operators = []
    single_qutrit_kraus_operator_weights = []
    two_qutrit_kraus_operators = []
    two_qutrit_kraus_operator_weights = []

    idle_channel_operators = []
    long_idle_channel_weights = []
    short_idle_channel_weights = []

    def pick_single_qutrit_gate_channel(self):
        index = weighted_draw(self.single_qutrit_kraus_operator_weights)
        return self.single_qutrit_kraus_operators[index]

    def pick_two_qutrit_gate_channel(self):
        index = weighted_draw(self.two_qutrit_kraus_operator_weights)
        return self.two_qutrit_kraus_operators[index]

    def pick_long_idle_channel(self, state, buffer, index):
        index = weighted_draw(self.long_idle_channel_weights)
        return self.idle_channel_operators[index]

    def pick_short_idle_channel(self, state, buffer, index):
        index = weighted_draw(self.short_idle_channel_weights)
        return self.idle_channel_operators[index]


X3 = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]])
Z3 = np.array([[1, 0, 0], [0, math.e ** (math.pi * 1j * -2.0/3.0), 0], [0, 0, math.e ** (math.pi * 1j * -4.0/3.0)]])
Y3 = X3 @ Z3
V3 = X3 @ Z3 @ Z3

class GenericQutritErrors(NoiseChannel):
    single_qutrit_kraus_operators = [np.eye(3), Z3, Z3 @ Z3, X3, X3 @ Z3, X3 @ Z3 @ Z3, X3 @ X3, X3 @ X3 @ Z3, X3 @ X3 @ Z3 @ Z3]
    two_qutrit_kraus_operators = [np.kron(np.eye(3), np.eye(3)), np.kron(np.eye(3), Z3), np.kron(np.eye(3), Z3 @ Z3), np.kron(np.eye(3), X3), np.kron(np.eye(3), X3 @ Z3), np.kron(np.eye(3), X3 @ Z3 @ Z3), np.kron(np.eye(3), X3 @ X3), np.kron(np.eye(3), X3 @ X3 @ Z3), np.kron(np.eye(3), X3 @ X3 @ Z3 @ Z3),
            np.kron(Z3, np.eye(3)), np.kron(Z3, Z3), np.kron(Z3, Z3 @ Z3), np.kron(Z3, X3), np.kron(Z3, X3 @ Z3), np.kron(Z3, X3 @ Z3 @ Z3), np.kron(Z3, X3 @ X3), np.kron(Z3, X3 @ X3 @ Z3), np.kron(Z3, X3 @ X3 @ Z3 @ Z3),
            np.kron(Z3 @ Z3, np.eye(3)), np.kron(Z3 @ Z3, Z3), np.kron(Z3 @ Z3, Z3 @ Z3), np.kron(Z3 @ Z3, X3), np.kron(Z3 @ Z3, X3 @ Z3), np.kron(Z3 @ Z3, X3 @ Z3 @ Z3), np.kron(Z3 @ Z3, X3 @ X3), np.kron(Z3 @ Z3, X3 @ X3 @ Z3), np.kron(Z3 @ Z3, X3 @ X3 @ Z3 @ Z3),
            np.kron(X3, np.eye(3)), np.kron(X3, Z3), np.kron(X3, Z3 @ Z3), np.kron(X3, X3), np.kron(X3, X3 @ Z3), np.kron(X3, X3 @ Z3 @ Z3), np.kron(X3, X3 @ X3), np.kron(X3, X3 @ X3 @ Z3), np.kron(X3, X3 @ X3 @ Z3 @ Z3),
            np.kron(X3 @ Z3, np.eye(3)), np.kron(X3 @ Z3, Z3), np.kron(X3 @ Z3, Z3 @ Z3), np.kron(X3 @ Z3, X3), np.kron(X3 @ Z3, X3 @ Z3), np.kron(X3 @ Z3, X3 @ Z3 @ Z3), np.kron(X3 @ Z3, X3 @ X3), np.kron(X3 @ Z3, X3 @ X3 @ Z3), np.kron(X3 @ Z3, X3 @ X3 @ Z3 @ Z3),
            np.kron(X3 @ Z3 @ Z3, np.eye(3)), np.kron(X3 @ Z3 @ Z3, Z3), np.kron(X3 @ Z3 @ Z3, Z3 @ Z3), np.kron(X3 @ Z3 @ Z3, X3), np.kron(X3 @ Z3 @ Z3, X3 @ Z3), np.kron(X3 @ Z3 @ Z3, X3 @ Z3 @ Z3), np.kron(X3 @ Z3 @ Z3, X3 @ X3), np.kron(X3 @ Z3 @ Z3, X3 @ X3 @ Z3), np.kron(X3 @ Z3 @ Z3, X3 @ X3 @ Z3 @ Z3),
            np.kron(X3 @ X3, np.eye(3)), np.kron(X3 @ X3, Z3), np.kron(X3 @ X3, Z3 @ Z3), np.kron(X3 @ X3, X3), np.kron(X3 @ X3, X3 @ Z3), np.kron(X3 @ X3, X3 @ Z3 @ Z3), np.kron(X3 @ X3, X3 @ X3), np.kron(X3 @ X3, X3 @ X3 @ Z3), np.kron(X3 @ X3, X3 @ X3 @ Z3 @ Z3),
            np.kron(X3 @ X3 @ Z3, np.eye(3)), np.kron(X3 @ X3 @ Z3, Z3), np.kron(X3 @ X3 @ Z3, Z3 @ Z3), np.kron(X3 @ X3 @ Z3, X3), np.kron(X3 @ X3 @ Z3, X3 @ Z3), np.kron(X3 @ X3 @ Z3, X3 @ Z3 @ Z3), np.kron(X3 @ X3 @ Z3, X3 @ X3), np.kron(X3 @ X3 @ Z3, X3 @ X3 @ Z3), np.kron(X3 @ X3 @ Z3, X3 @ X3 @ Z3 @ Z3),
            np.kron(X3 @ X3 @ Z3 @ Z3, np.eye(3)), np.kron(X3 @ X3 @ Z3 @ Z3, Z3), np.kron(X3 @ X3 @ Z3 @ Z3, Z3 @ Z3), np.kron(X3 @ X3 @ Z3 @ Z3, X3), np.kron(X3 @ X3 @ Z3 @ Z3, X3 @ Z3), np.kron(X3 @ X3 @ Z3 @ Z3, X3 @ Z3 @ Z3), np.kron(X3 @ X3 @ Z3 @ Z3, X3 @ X3), np.kron(X3 @ X3 @ Z3 @ Z3, X3 @ X3 @ Z3), np.kron(X3 @ X3 @ Z3 @ Z3, X3 @ X3 @ Z3 @ Z3)]

    def pick_long_idle_channel(self, state, buffer, index):
        weights = []
        for gate_error_matrix in self.long_idle_channel_operators:
            gate_error_matrix = gate_error_matrix.astype(np.complex128).reshape((3,) * 2)
            linalg.targeted_left_multiply(gate_error_matrix, state[:], [index], out=buffer)
            weights.append(np.linalg.norm(buffer) ** 2)

        index = weighted_draw(weights)
        return self.short_idle_channel_operators[index]

    def pick_short_idle_channel(self, state, buffer, index):
        weights = []
        for gate_error_matrix in self.short_idle_channel_operators:
            gate_error_matrix = gate_error_matrix.astype(np.complex128).reshape((3,) * 2)
            linalg.targeted_left_multiply(gate_error_matrix, state[:], [index], out=buffer)
            weights.append(np.linalg.norm(buffer) ** 2)

        index = weighted_draw(weights)
        return self.long_idle_channel_operators[index]


class CurrentSuperconductingQCErrors(GenericQutritErrors):
    p_1 = .001 / 3  # single qubit gate error  (https://arxiv.org/pdf/1702.01852.pdf and www.research.ibm.com/ibm-q/technology/devices)
                    # division by 3 because 3 possible error channels for qubits
    p_2 = .01 / 15  # same references, division by 15 because 15 error channels for qubits
    single_qutrit_kraus_operator_weights = [1 - 8*p_1] + 8 * [p_1]
    two_qutrit_kraus_operator_weights = [1 - 80*p_2] + 80 * [p_2]
    # gamma_m = 1 - e^(-m * dt / T1), where dt is gate time duration (https://web.physics.ucsb.edu/~martinisgroup/papers/Ghosh2013b.pdf)
    # Here, I picked T1 = 100 microseconds (representative from https://www.research.ibm.com/ibm-q/technology/devices/)
    # and dt = 100 ns for single-qudit gates and 300 ns for two-qudit gates (https://arxiv.org/pdf/1702.01852.pdf)
    gamma_1_short = 1 - math.exp(-1 *  100.0 / 100000.0)
    gamma_1_long = 1 - math.exp(-1 * 300.0 / 100000.0)
    gamma_2_short = 1 - math.exp(-2 *  100.0 / 100000.0)
    gamma_2_long = 1 - math.exp(-2 * 300.0 / 100000.0)
    short_idle_channel_operators = [np.array([[1,0,0],[0,(1-gamma_1_short)**.5,0],[0,0,(1-gamma_2_short)**.5]]), np.array([[0,gamma_1_short**0.5,0],[0,0,0],[0,0,0]]), np.array([[0,0,gamma_2_short**0.5],[0,0,0],[0,0,0]])]
    long_idle_channel_operators = [np.array([[1,0,0],[0,(1-gamma_1_long)**.5,0],[0,0,(1-gamma_2_long)**.5]]), np.array([[0,gamma_1_long**0.5,0],[0,0,0],[0,0,0]]), np.array([[0,0,gamma_2_long**0.5],[0,0,0],[0,0,0]])]


class FutureSuperconductingQCErrors(GenericQutritErrors):
    # Here, I 10x'ed T1 and 1/10x'ed the p's
    p_1 = .0001 / 3
    p_2 = .001 / 15
    single_qutrit_kraus_operator_weights = [1 - 8*p_1] + 8 * [p_1]
    two_qutrit_kraus_operator_weights = [1 - 80*p_2] + 80 * [p_2]
    # Here, I picked T1 = 1000 microseconds 
    gamma_1_short = 1 - math.exp(-1 *  100.0 / 1000000.0)
    gamma_1_long = 1 - math.exp(-1 * 300.0 / 1000000.0)
    gamma_2_short = 1 - math.exp(-2 *  100.0 / 1000000.0)
    gamma_2_long = 1 - math.exp(-2 * 300.0 / 1000000.0)
    short_idle_channel_operators = [np.array([[1,0,0],[0,(1-gamma_1_short)**.5,0],[0,0,(1-gamma_2_short)**.5]]), np.array([[0,gamma_1_short**0.5,0],[0,0,0],[0,0,0]]), np.array([[0,0,gamma_2_short**0.5],[0,0,0],[0,0,0]])]
    long_idle_channel_operators = [np.array([[1,0,0],[0,(1-gamma_1_long)**.5,0],[0,0,(1-gamma_2_long)**.5]]), np.array([[0,gamma_1_long**0.5,0],[0,0,0],[0,0,0]]), np.array([[0,0,gamma_2_long**0.5],[0,0,0],[0,0,0]])]


class FutureSuperconductingQCErrorsBetterT1(GenericQutritErrors):
    p_1 = .0001 / 3
    p_2 = .001 / 15
    single_qutrit_kraus_operator_weights = [1 - 8*p_1] + 8 * [p_1]
    two_qutrit_kraus_operator_weights = [1 - 80*p_2] + 80 * [p_2]
    # Here, I picked T1 = 10000 microseconds 
    gamma_1_short = 1 - math.exp(-1 *  100.0 / 10000000.0)
    gamma_1_long = 1 - math.exp(-1 * 300.0 / 10000000.0)
    gamma_2_short = 1 - math.exp(-2 *  100.0 / 10000000.0)
    gamma_2_long = 1 - math.exp(-2 * 300.0 / 10000000.0)
    short_idle_channel_operators = [np.array([[1,0,0],[0,(1-gamma_1_short)**.5,0],[0,0,(1-gamma_2_short)**.5]]), np.array([[0,gamma_1_short**0.5,0],[0,0,0],[0,0,0]]), np.array([[0,0,gamma_2_short**0.5],[0,0,0],[0,0,0]])]
    long_idle_channel_operators = [np.array([[1,0,0],[0,(1-gamma_1_long)**.5,0],[0,0,(1-gamma_2_long)**.5]]), np.array([[0,gamma_1_long**0.5,0],[0,0,0],[0,0,0]]), np.array([[0,0,gamma_2_long**0.5],[0,0,0],[0,0,0]])]


class FutureSuperconductingQCErrorsBetterGates(GenericQutritErrors):
    p_1 = .00001 / 3
    p_2 = .0001 / 15
    single_qutrit_kraus_operator_weights = [1 - 8*p_1] + 8 * [p_1]
    two_qutrit_kraus_operator_weights = [1 - 80*p_2] + 80 * [p_2]
    # Here, I picked T1 = 1000 microseconds 
    gamma_1_short = 1 - math.exp(-1 *  100.0 / 1000000.0)
    gamma_1_long = 1 - math.exp(-1 * 300.0 / 1000000.0)
    gamma_2_short = 1 - math.exp(-2 *  100.0 / 1000000.0)
    gamma_2_long = 1 - math.exp(-2 * 300.0 / 1000000.0)
    short_idle_channel_operators = [np.array([[1,0,0],[0,(1-gamma_1_short)**.5,0],[0,0,(1-gamma_2_short)**.5]]), np.array([[0,gamma_1_short**0.5,0],[0,0,0],[0,0,0]]), np.array([[0,0,gamma_2_short**0.5],[0,0,0],[0,0,0]])]
    long_idle_channel_operators = [np.array([[1,0,0],[0,(1-gamma_1_long)**.5,0],[0,0,(1-gamma_2_long)**.5]]), np.array([[0,gamma_1_long**0.5,0],[0,0,0],[0,0,0]]), np.array([[0,0,gamma_2_long**0.5],[0,0,0],[0,0,0]])]


class FutureSuperconductingQCErrorsBetterT1AndGates(GenericQutritErrors):
    p_1 = .00001 / 3
    p_2 = .0001 / 15
    single_qutrit_kraus_operator_weights = [1 - 8*p_1] + 8 * [p_1]
    two_qutrit_kraus_operator_weights = [1 - 80*p_2] + 80 * [p_2]
    # Here, I picked T1 = 10000 microseconds 
    gamma_1_short = 1 - math.exp(-1 *  100.0 / 10000000.0)
    gamma_1_long = 1 - math.exp(-1 * 300.0 / 10000000.0)
    gamma_2_short = 1 - math.exp(-2 *  100.0 / 10000000.0)
    gamma_2_long = 1 - math.exp(-2 * 300.0 / 10000000.0)
    short_idle_channel_operators = [np.array([[1,0,0],[0,(1-gamma_1_short)**.5,0],[0,0,(1-gamma_2_short)**.5]]), np.array([[0,gamma_1_short**0.5,0],[0,0,0],[0,0,0]]), np.array([[0,0,gamma_2_short**0.5],[0,0,0],[0,0,0]])]
    long_idle_channel_operators = [np.array([[1,0,0],[0,(1-gamma_1_long)**.5,0],[0,0,(1-gamma_2_long)**.5]]), np.array([[0,gamma_1_long**0.5,0],[0,0,0],[0,0,0]]), np.array([[0,0,gamma_2_long**0.5],[0,0,0],[0,0,0]])]


class DressedQutritErrors(NoiseChannel):
    idle_channel_operators = [Z3, Z3 @ Z3, np.eye(3)]
    long_idle_channel_weights = [0.0000228617, 0.0000228617, 0.9999542766]
    short_idle_channel_weights = [5.71579E-10, 5.71579E-10, 0.99999999885]

    single_qutrit_kraus_operators = [X3, X3 @ X3, Z3, Z3 @ Z3, Y3, Y3 @ Y3, V3, V3 @ V3, np.eye(3)]
    single_qutrit_kraus_operator_weights = [8.07695E-7, 8.35653E-7, 4.49109E-7, 4.49109E-7, 8.07695E-7, 8.35653E-7, 8.07695E-7, 8.35653E-7, 0.999846624680123]

    XX_weights = [4.517809752636722e-10,4.674189903317726e-10,2.512069977868293e-10,2.512069977868293e-10,4.517809752636722e-10,4.674189903317726e-10,4.517809752636722e-10,4.674189903317726e-10,0.000021251879958915915]
    X2X_weights = [4.674189903317726e-10,4.835983020207133e-10,2.5990231483578203e-10,2.5990231483578203e-10,4.674189903317726e-10,4.835983020207133e-10,4.674189903317726e-10,4.835983020207133e-10,0.00002198749574891023]
    ZX_weights = [2.512069977868293e-10,2.5990231483578203e-10,1.3968041859275328e-10,1.3968041859275328e-10,2.512069977868293e-10,2.5990231483578203e-10,2.512069977868293e-10,2.5990231483578203e-10,0.000011816834382389788]
    Z2X_weights = [2.512069977868293e-10,2.5990231483578203e-10,1.3968041859275328e-10,1.3968041859275328e-10,2.512069977868293e-10,2.5990231483578203e-10,2.512069977868293e-10,2.5990231483578203e-10,0.000011816834382389788]
    YX_weights = [4.517809752636722e-10,4.674189903317726e-10,2.512069977868293e-10,2.512069977868293e-10,4.517809752636722e-10,4.674189903317726e-10,4.517809752636722e-10,4.674189903317726e-10,0.000021251879958915915]
    Y2X_weights = [4.674189903317726e-10,4.835983020207133e-10,2.5990231483578203e-10,2.5990231483578203e-10,4.674189903317726e-10,4.835983020207133e-10,4.674189903317726e-10,4.835983020207133e-10,0.00002198749574891023]
    VX_weights = [4.517809752636722e-10,4.674189903317726e-10,2.512069977868293e-10,2.512069977868293e-10,4.517809752636722e-10,4.674189903317726e-10,4.517809752636722e-10,4.674189903317726e-10,0.000021251879958915915]
    V2X_weights = [4.674189903317726e-10,4.835983020207133e-10,2.5990231483578203e-10,2.5990231483578203e-10,4.674189903317726e-10,4.835983020207133e-10,4.674189903317726e-10,4.835983020207133e-10,0.00002198749574891023]
    TX_weights = [0.000021251879958915915,0.00002198749574891023,0.000011816834382389788,0.000011816834382389788,0.000021251879958915915,0.00002198749574891023,0.000021251879958915915,0.00002198749574891023,0.9996932728842347]

    XX_operators = [np.kron(X3, X3), np.kron(X3, X3 @ X3), np.kron(X3, Z3), np.kron(X3, Z3 @ Z3), np.kron(X3, Y3), np.kron(X3, Y3 @ Y3), np.kron(X3, V3), np.kron(X3, V3 @ V3), np.kron(X3, np.eye(3))]
    X2X_operators = [np.kron(X3 @ X3, X3), np.kron(X3 @ X3, X3 @ X3), np.kron(X3 @ X3, Z3), np.kron(X3 @ X3, Z3 @ Z3), np.kron(X3 @ X3, Y3), np.kron(X3 @ X3, Y3 @ Y3), np.kron(X3 @ X3, V3), np.kron(X3 @ X3, V3 @ V3), np.kron(X3 @ X3, np.eye(3))]
    ZX_operators = [np.kron(Z3, X3), np.kron(Z3, X3 @ X3), np.kron(Z3, Z3), np.kron(Z3, Z3 @ Z3), np.kron(Z3, Y3), np.kron(Z3, Y3 @ Y3), np.kron(Z3, V3), np.kron(Z3, V3 @ V3), np.kron(Z3, np.eye(3))]
    Z2X_operators = [np.kron(Z3 @ Z3, X3), np.kron(Z3 @ Z3, X3 @ X3), np.kron(Z3 @ Z3, Z3), np.kron(Z3 @ Z3, Z3 @ Z3), np.kron(Z3 @ Z3, Y3), np.kron(Z3 @ Z3, Y3 @ Y3), np.kron(Z3 @ Z3, V3), np.kron(Z3 @ Z3, V3 @ V3), np.kron(Z3 @ Z3, np.eye(3))]
    YX_operators = [np.kron(Y3, X3), np.kron(Y3, X3 @ X3), np.kron(Y3, Z3), np.kron(Y3, Z3 @ Z3), np.kron(Y3, Y3), np.kron(Y3, Y3 @ Y3), np.kron(Y3, V3), np.kron(Y3, V3 @ V3), np.kron(Y3, np.eye(3))]
    Y2X_operators = [np.kron(Y3 @ Y3, X3), np.kron(Y3 @ Y3, X3 @ X3), np.kron(Y3 @ Y3, Z3), np.kron(Y3 @ Y3, Z3 @ Z3), np.kron(Y3 @ Y3, Y3), np.kron(Y3 @ Y3, Y3 @ Y3), np.kron(Y3 @ Y3, V3), np.kron(Y3 @ Y3, V3 @ V3), np.kron(Y3 @ Y3, np.eye(3))]
    VX_operators = [np.kron(V3, X3), np.kron(V3, X3 @ X3), np.kron(V3, Z3), np.kron(V3, Z3 @ Z3), np.kron(V3, Y3), np.kron(V3, Y3 @ Y3), np.kron(V3, V3), np.kron(V3, V3 @ V3), np.kron(V3, np.eye(3))]
    V2X_operators = [np.kron(V3 @ V3, X3), np.kron(V3 @ V3, X3 @ X3), np.kron(V3 @ V3, Z3), np.kron(V3 @ V3, Z3 @ Z3), np.kron(V3 @ V3, Y3), np.kron(V3 @ V3, Y3 @ Y3), np.kron(V3 @ V3, V3), np.kron(V3 @ V3, V3 @ V3), np.kron(V3 @ V3, np.eye(3))]
    TX_operators = [np.kron(np.eye(3), X3), np.kron(np.eye(3), X3 @ X3), np.kron(np.eye(3), Z3), np.kron(np.eye(3), Z3 @ Z3), np.kron(np.eye(3), Y3), np.kron(np.eye(3), Y3 @ Y3), np.kron(np.eye(3), V3), np.kron(np.eye(3), V3 @ V3), np.kron(np.eye(3), np.eye(3))]

    two_qutrit_kraus_operators = XX_operators + X2X_operators + ZX_operators + Z2X_operators + YX_operators + Y2X_operators + VX_operators + V2X_operators + TX_operators
    two_qutrit_kraus_operator_weights =  XX_weights + X2X_weights + ZX_weights + Z2X_weights + YX_weights + Y2X_weights + VX_weights + V2X_weights + TX_weights


class BareQutritErrors(NoiseChannel):
    idle_channel_operators = [Z3, Z3 @ Z3, np.eye(3)]
    long_idle_channel_weights = [0, 0.00007751, 0.99992249] 
    short_idle_channel_weights = [0, 0.0000000019379, 0.99999999806]

    single_qutrit_kraus_operators = [X3, X3 @ X3, Z3, Z3 @ Z3, Y3, Y3 @ Y3, V3, V3 @ V3, np.eye(3)]
    single_qutrit_kraus_operator_weights = [8.076953189667142e-7,8.356530070058442e-7,4.4910858870426395e-7,4.4910858870426395e-7,8.076953189667142e-7,8.356530070058442e-7,8.076953189667142e-7,8.356530070058442e-7,0.999846624680123]

    XX_weights = [4.517809752636722e-10,4.674189903317726e-10,2.512069977868293e-10,2.512069977868293e-10,4.517809752636722e-10,4.674189903317726e-10,4.517809752636722e-10,4.674189903317726e-10,0.000021251879958915915]
    X2X_weights = [4.674189903317726e-10,4.835983020207133e-10,2.5990231483578203e-10,2.5990231483578203e-10,4.674189903317726e-10,4.835983020207133e-10,4.674189903317726e-10,4.835983020207133e-10,0.00002198749574891023]
    ZX_weights = [2.512069977868293e-10,2.5990231483578203e-10,1.3968041859275328e-10,1.3968041859275328e-10,2.512069977868293e-10,2.5990231483578203e-10,2.512069977868293e-10,2.5990231483578203e-10,0.000011816834382389788]
    Z2X_weights = [2.512069977868293e-10,2.5990231483578203e-10,1.3968041859275328e-10,1.3968041859275328e-10,2.512069977868293e-10,2.5990231483578203e-10,2.512069977868293e-10,2.5990231483578203e-10,0.000011816834382389788]
    YX_weights = [4.517809752636722e-10,4.674189903317726e-10,2.512069977868293e-10,2.512069977868293e-10,4.517809752636722e-10,4.674189903317726e-10,4.517809752636722e-10,4.674189903317726e-10,0.000021251879958915915]
    Y2X_weights = [4.674189903317726e-10,4.835983020207133e-10,2.5990231483578203e-10,2.5990231483578203e-10,4.674189903317726e-10,4.835983020207133e-10,4.674189903317726e-10,4.835983020207133e-10,0.00002198749574891023]
    VX_weights = [4.517809752636722e-10,4.674189903317726e-10,2.512069977868293e-10,2.512069977868293e-10,4.517809752636722e-10,4.674189903317726e-10,4.517809752636722e-10,4.674189903317726e-10,0.000021251879958915915]
    V2X_weights = [4.674189903317726e-10,4.835983020207133e-10,2.5990231483578203e-10,2.5990231483578203e-10,4.674189903317726e-10,4.835983020207133e-10,4.674189903317726e-10,4.835983020207133e-10,0.00002198749574891023]
    TX_weights = [0.000021251879958915915,0.00002198749574891023,0.000011816834382389788,0.000011816834382389788,0.000021251879958915915,0.00002198749574891023,0.000021251879958915915,0.00002198749574891023,0.9996932728842347]

    XX_operators = [np.kron(X3, X3), np.kron(X3, X3 @ X3), np.kron(X3, Z3), np.kron(X3, Z3 @ Z3), np.kron(X3, Y3), np.kron(X3, Y3 @ Y3), np.kron(X3, V3), np.kron(X3, V3 @ V3), np.kron(X3, np.eye(3))]
    X2X_operators = [np.kron(X3 @ X3, X3), np.kron(X3 @ X3, X3 @ X3), np.kron(X3 @ X3, Z3), np.kron(X3 @ X3, Z3 @ Z3), np.kron(X3 @ X3, Y3), np.kron(X3 @ X3, Y3 @ Y3), np.kron(X3 @ X3, V3), np.kron(X3 @ X3, V3 @ V3), np.kron(X3 @ X3, np.eye(3))]
    ZX_operators = [np.kron(Z3, X3), np.kron(Z3, X3 @ X3), np.kron(Z3, Z3), np.kron(Z3, Z3 @ Z3), np.kron(Z3, Y3), np.kron(Z3, Y3 @ Y3), np.kron(Z3, V3), np.kron(Z3, V3 @ V3), np.kron(Z3, np.eye(3))]
    Z2X_operators = [np.kron(Z3 @ Z3, X3), np.kron(Z3 @ Z3, X3 @ X3), np.kron(Z3 @ Z3, Z3), np.kron(Z3 @ Z3, Z3 @ Z3), np.kron(Z3 @ Z3, Y3), np.kron(Z3 @ Z3, Y3 @ Y3), np.kron(Z3 @ Z3, V3), np.kron(Z3 @ Z3, V3 @ V3), np.kron(Z3 @ Z3, np.eye(3))]
    YX_operators = [np.kron(Y3, X3), np.kron(Y3, X3 @ X3), np.kron(Y3, Z3), np.kron(Y3, Z3 @ Z3), np.kron(Y3, Y3), np.kron(Y3, Y3 @ Y3), np.kron(Y3, V3), np.kron(Y3, V3 @ V3), np.kron(Y3, np.eye(3))]
    Y2X_operators = [np.kron(Y3 @ Y3, X3), np.kron(Y3 @ Y3, X3 @ X3), np.kron(Y3 @ Y3, Z3), np.kron(Y3 @ Y3, Z3 @ Z3), np.kron(Y3 @ Y3, Y3), np.kron(Y3 @ Y3, Y3 @ Y3), np.kron(Y3 @ Y3, V3), np.kron(Y3 @ Y3, V3 @ V3), np.kron(Y3 @ Y3, np.eye(3))]
    VX_operators = [np.kron(V3, X3), np.kron(V3, X3 @ X3), np.kron(V3, Z3), np.kron(V3, Z3 @ Z3), np.kron(V3, Y3), np.kron(V3, Y3 @ Y3), np.kron(V3, V3), np.kron(V3, V3 @ V3), np.kron(V3, np.eye(3))]
    V2X_operators = [np.kron(V3 @ V3, X3), np.kron(V3 @ V3, X3 @ X3), np.kron(V3 @ V3, Z3), np.kron(V3 @ V3, Z3 @ Z3), np.kron(V3 @ V3, Y3), np.kron(V3 @ V3, Y3 @ Y3), np.kron(V3 @ V3, V3), np.kron(V3 @ V3, V3 @ V3), np.kron(V3 @ V3, np.eye(3))]
    TX_operators = [np.kron(np.eye(3), X3), np.kron(np.eye(3), X3 @ X3), np.kron(np.eye(3), Z3), np.kron(np.eye(3), Z3 @ Z3), np.kron(np.eye(3), Y3), np.kron(np.eye(3), Y3 @ Y3), np.kron(np.eye(3), V3), np.kron(np.eye(3), V3 @ V3), np.kron(np.eye(3), np.eye(3))]

    two_qutrit_kraus_operators = XX_operators + X2X_operators + ZX_operators + Z2X_operators + YX_operators + Y2X_operators + VX_operators + V2X_operators + TX_operators
    two_qutrit_kraus_operator_weights =  XX_weights + X2X_weights + ZX_weights + Z2X_weights + YX_weights + Y2X_weights + VX_weights + V2X_weights + TX_weights


class PauliDepolarizing(NoiseChannel):
    pass
