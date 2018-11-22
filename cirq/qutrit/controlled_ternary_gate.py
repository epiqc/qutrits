
import itertools

from cirq import ops
from cirq.qutrit import raw_types
from cirq.qutrit import common_gates
import math, numpy as np


class ControlledTernaryGate(raw_types.TernaryLogicGate,
                            ops.CompositeGate,
                            ops.ReversibleEffect,
                            ops.TextDiagrammable):
    def __init__(self, base_gate, control_values):
        """ Args:
                control_values: E.g. [(2,), (1,), (0,1)] for a three
                control gate that triggers if the first qutrit is 2, the
                second is 1 and the third is either 0 or 1.
        """
        self.base_gate = base_gate
        self.control_values = control_values

        def validate_trits(self, trits):
            pass

        def applied_to_trits(self, trits):
            pass

    def default_decompose(self, qutrits):
        # qutrits are control, target or control, control, target
        assert len(self.control_values) in [1, 2]
        assert len(qutrits) == len(self.control_values) + 1

        if len(self.control_values) == 1:
            if self.control_values == ((2,),) and self.base_gate == common_gates.F01:
                yield C2F01()(*qutrits)
            elif self.control_values == ((1,),) and self.base_gate == common_gates.PlusOne:
                yield C1PlusOne()(*qutrits)
            elif self.control_values == ((1,),) and self.base_gate == common_gates.MinusOne:
                yield C1MinusOne()(*qutrits)
            else:
                assert False, "control_values: %s, base_gate: %s" % (self.control_values, self.base_gate)

        elif len(self.control_values) == 2:
            if self.control_values == ((1,), (1,)) and self.base_gate == common_gates.PlusOne:
                yield C1C1PlusOne()(*qutrits)
            elif self.control_values == ((1,), (1,)) and self.base_gate == common_gates.MinusOne:
                yield C1C1MinusOne()(*qutrits)
            elif self.control_values == ((2,), (2,)) and self.base_gate == common_gates.PlusOne:
                yield C2C2PlusOne()(*qutrits)
            elif self.control_values == ((2,), (2,)) and self.base_gate == common_gates.MinusOne:
                yield C2C2MinusOne()(*qutrits)
            else:
                assert False, "control_values: %s, base_gate: %s" % (self.control_values, self.base_gate)

        else:
            assert False, 'more than two controls'


    @staticmethod
    def all_controlled_gates(base_gate, base_name, max_controls=1,
            control_types=((0,), (1,), (2,), (0,1), (0,2), (1,2))):
        gates = {}
        for control_num in range(1, max_controls+1):
            for controls in itertools.product(control_types,
                                              repeat=control_num):
                gate_pre = ''.join('C'+''.join(map(str, (c for c in control)))
                                   for control in controls)
                gate_name = gate_pre + base_name
                gate = ControlledTernaryGate(base_gate, controls)
                gates[gate_name] = gate
        return gates

    def inverse(self):
        return ControlledTernaryGate(self.base_gate.inverse(),
                                     self.control_values)

    def _control_symbols(self):
        return tuple(','.join(map(str, vals))
                     for vals in self.control_values)

    def text_diagram_info(self, args):
        base_info = self.base_gate.text_diagram_info(args)
        c_syms = self._control_symbols()
        return ops.TextDiagramInfo(c_syms+base_info.wire_symbols,
                                   exponent=base_info.exponent,
                                   connected=True)

    def validate_trits(self, trits):
        super().validate_trits(trits)
        self.base_gate.validate_trits(trits[len(self.control_values):])

    def applied_to_trits(self, trits):
        len_trits = len(trits)
        controls = trits[:len(self.control_values)]
        control_active = all(
            trit in matches
            for trit, matches in zip(controls, self.control_values)
        )
        if control_active:
            changed_trits = self.base_gate.applied_to_trits(
                                        trits[len(self.control_values):])
            trits[len(self.control_values):] = changed_trits
        return trits


class C1C1PlusOne(raw_types.TernaryLogicGate,
                  ops.CompositeGate):
    def default_decompose(self, qutrits):
        yield Ry12(-math.pi/4)(qutrits[2])
        yield C1F12()(qutrits[1], qutrits[2])
        yield Ry12(-math.pi/4)(qutrits[2])
        yield C1F12()(qutrits[0], qutrits[2])
        yield Ry12(math.pi/4)(qutrits[2])
        yield C1F12()(qutrits[1], qutrits[2])
        yield Ry12Pi4Ry01Pi4()(qutrits[2])
        yield C1F01()(qutrits[1], qutrits[2])
        yield Ry01(math.pi/4)(qutrits[2])
        yield C1F01()(qutrits[0], qutrits[2])
        yield Ry01(-math.pi/4)(qutrits[2])
        yield C1F01()(qutrits[1], qutrits[2])
        yield Ry01(-math.pi/4)(qutrits[2])


class C2C2PlusOne(raw_types.TernaryLogicGate,
                  ops.CompositeGate):
    def default_decompose(self, qutrits):
        yield Ry12(-math.pi/4)(qutrits[2])
        yield C2F12()(qutrits[1], qutrits[2])
        yield Ry12(-math.pi/4)(qutrits[2])
        yield C2F12()(qutrits[0], qutrits[2])
        yield Ry12(math.pi/4)(qutrits[2])
        yield C2F12()(qutrits[1], qutrits[2])
        yield Ry12Pi4Ry01Pi4()(qutrits[2])
        yield C2F01()(qutrits[1], qutrits[2])
        yield Ry01(math.pi/4)(qutrits[2])
        yield C2F01()(qutrits[0], qutrits[2])
        yield Ry01(-math.pi/4)(qutrits[2])
        yield C2F01()(qutrits[1], qutrits[2])
        yield Ry01(-math.pi/4)(qutrits[2])

class C1C1MinusOne(raw_types.TernaryLogicGate,
                   ops.CompositeGate):
    def default_decompose(self, qutrits):
        yield Ry01(math.pi/4)(qutrits[2])
        yield C1F01()(qutrits[1], qutrits[2])
        yield Ry01(math.pi/4)(qutrits[2])
        yield C1F01()(qutrits[0], qutrits[2])
        yield Ry01(-math.pi/4)(qutrits[2])
        yield C1F01()(qutrits[1], qutrits[2])
        yield Ry01MinusPi4Ry12MinusPi4()(qutrits[2])
        yield C1F12()(qutrits[1], qutrits[2])
        yield Ry12(-math.pi/4)(qutrits[2])
        yield C1F12()(qutrits[0], qutrits[2])
        yield Ry12(math.pi/4)(qutrits[2])
        yield C1F12()(qutrits[1], qutrits[2])
        yield Ry12(math.pi/4)(qutrits[2])

class C2C2MinusOne(raw_types.TernaryLogicGate,
                   ops.CompositeGate):
    def default_decompose(self, qutrits):
        yield Ry01(math.pi/4)(qutrits[2])
        yield C2F01()(qutrits[1], qutrits[2])
        yield Ry01(math.pi/4)(qutrits[2])
        yield C2F01()(qutrits[0], qutrits[2])
        yield Ry01(-math.pi/4)(qutrits[2])
        yield C2F01()(qutrits[1], qutrits[2])
        yield Ry01MinusPi4Ry12MinusPi4()(qutrits[2])
        yield C2F12()(qutrits[1], qutrits[2])
        yield Ry12(-math.pi/4)(qutrits[2])
        yield C2F12()(qutrits[0], qutrits[2])
        yield Ry12(math.pi/4)(qutrits[2])
        yield C2F12()(qutrits[1], qutrits[2])
        yield Ry12(math.pi/4)(qutrits[2])

class Ry01(raw_types.TernaryLogicGate):
    def __init__(self, theta):
        self.theta = theta

    def _unitary_(self):
        theta = self.theta
        return np.array([[math.cos(theta/2.0), -math.sin(theta/2.0), 0],
                         [math.sin(theta/2.0), math.cos(theta/2.0), 0],
                         [0, 0, 1]])

class Ry12(raw_types.TernaryLogicGate):
    def __init__(self, theta):
        self.theta = theta

    def _unitary_(self):
        theta = self.theta
        return np.array([[1, 0, 0],
                         [0, math.cos(theta/2.0), -math.sin(theta/2.0)],
                         [0, math.sin(theta/2.0), math.cos(theta/2.0)]])

class Ry01MinusPi4Ry12MinusPi4(raw_types.TernaryLogicGate):
    def _unitary_(self):
        return np.dot(Ry12(-math.pi/4)._unitary_(), Ry01(-math.pi/4)._unitary_())

class Ry12Pi4Ry01Pi4(raw_types.TernaryLogicGate):
    def _unitary_(self):
        return np.dot(Ry01(math.pi/4)._unitary_(), Ry12(math.pi/4)._unitary_())

class C1F01(raw_types.TernaryLogicGate):
    def _unitary_(self):
        return np.array([[1, 0, 0, 0, 0, 0, 0, 0, 0],
                         [0, 1, 0, 0, 0, 0, 0, 0, 0],
                         [0, 0, 1, 0, 0, 0, 0, 0, 0],
                         [0, 0, 0, 0, 1, 0, 0, 0, 0],
                         [0, 0, 0, 1, 0, 0, 0, 0, 0],
                         [0, 0, 0, 0, 0, 1, 0, 0, 0],
                         [0, 0, 0, 0, 0, 0, 1, 0, 0],
                         [0, 0, 0, 0, 0, 0, 0, 1, 0],
                         [0, 0, 0, 0, 0, 0, 0, 0, 1]])

class C2F01(raw_types.TernaryLogicGate):
    def _unitary_(self):
        return np.array([[1, 0, 0, 0, 0, 0, 0, 0, 0],
                         [0, 1, 0, 0, 0, 0, 0, 0, 0],
                         [0, 0, 1, 0, 0, 0, 0, 0, 0],
                         [0, 0, 0, 1, 0, 0, 0, 0, 0],
                         [0, 0, 0, 0, 1, 0, 0, 0, 0],
                         [0, 0, 0, 0, 0, 1, 0, 0, 0],
                         [0, 0, 0, 0, 0, 0, 0, 1, 0],
                         [0, 0, 0, 0, 0, 0, 1, 0, 0],
                         [0, 0, 0, 0, 0, 0, 0, 0, 1]])

class C1F12(raw_types.TernaryLogicGate):
    def _unitary_(self):
        return np.array([[1, 0, 0, 0, 0, 0, 0, 0, 0],
                         [0, 1, 0, 0, 0, 0, 0, 0, 0],
                         [0, 0, 1, 0, 0, 0, 0, 0, 0],
                         [0, 0, 0, 1, 0, 0, 0, 0, 0],
                         [0, 0, 0, 0, 0, 1, 0, 0, 0],
                         [0, 0, 0, 0, 1, 0, 0, 0, 0],
                         [0, 0, 0, 0, 0, 0, 1, 0, 0],
                         [0, 0, 0, 0, 0, 0, 0, 1, 0],
                         [0, 0, 0, 0, 0, 0, 0, 0, 1]])

class C2F12(raw_types.TernaryLogicGate):
    def _unitary_(self):
        return np.array([[1, 0, 0, 0, 0, 0, 0, 0, 0],
                         [0, 1, 0, 0, 0, 0, 0, 0, 0],
                         [0, 0, 1, 0, 0, 0, 0, 0, 0],
                         [0, 0, 0, 1, 0, 0, 0, 0, 0],
                         [0, 0, 0, 0, 1, 0, 0, 0, 0],
                         [0, 0, 0, 0, 0, 1, 0, 0, 0],
                         [0, 0, 0, 0, 0, 0, 1, 0, 0],
                         [0, 0, 0, 0, 0, 0, 0, 0, 1],
                         [0, 0, 0, 0, 0, 0, 0, 1, 0]])

class C1PlusOne(raw_types.TernaryLogicGate):
    def _unitary_(self):
        return np.array([[1, 0, 0, 0, 0, 0, 0, 0, 0],
                         [0, 1, 0, 0, 0, 0, 0, 0, 0],
                         [0, 0, 1, 0, 0, 0, 0, 0, 0],
                         [0, 0, 0, 0, 0, 1, 0, 0, 0],
                         [0, 0, 0, 1, 0, 0, 0, 0, 0],
                         [0, 0, 0, 0, 1, 0, 0, 0, 0],
                         [0, 0, 0, 0, 0, 0, 1, 0, 0],
                         [0, 0, 0, 0, 0, 0, 0, 1, 0],
                         [0, 0, 0, 0, 0, 0, 0, 0, 1]])


class C1MinusOne(raw_types.TernaryLogicGate):
    def _unitary_(self):
        return np.array([[1, 0, 0, 0, 0, 0, 0, 0, 0],
                         [0, 1, 0, 0, 0, 0, 0, 0, 0],
                         [0, 0, 1, 0, 0, 0, 0, 0, 0],
                         [0, 0, 0, 0, 1, 0, 0, 0, 0],
                         [0, 0, 0, 0, 0, 1, 0, 0, 0],
                         [0, 0, 0, 1, 0, 0, 0, 0, 0],
                         [0, 0, 0, 0, 0, 0, 1, 0, 0],
                         [0, 0, 0, 0, 0, 0, 0, 1, 0],
                         [0, 0, 0, 0, 0, 0, 0, 0, 1]])
