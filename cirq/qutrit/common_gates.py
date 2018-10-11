
from cirq import ops
from cirq.qutrit import raw_types


class PlusOneGate(raw_types.TernaryLogicGate,
                  ops.ReversibleEffect,
                  ops.TextDiagrammable):
    def inverse(self):
        return MinusOne

    def text_diagram_info(self, args):
        return ops.TextDiagramInfo(('[+1]',))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) == 1, 'Gate only operates on one qutrit'

    def applied_to_trits(self, trits):
        return [(trits[0] + 1) % 3]


class MinusOneGate(raw_types.TernaryLogicGate,
                   ops.ReversibleEffect,
                   ops.TextDiagrammable):
    def inverse(self):
        return PlusOne

    def text_diagram_info(self, args):
        return ops.TextDiagramInfo(('[-1]',))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) == 1, 'Gate only operates on one qutrit'

    def applied_to_trits(self, trits):
        return [(trits[0] - 1) % 3]


class Flip01Gate(raw_types.TernaryLogicGate,
                 ops.ReversibleEffect,
                 ops.TextDiagrammable):
    def inverse(self):
        return self

    def text_diagram_info(self, args):
        return ops.TextDiagramInfo(('[F01]',))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) == 1, 'Gate only operates on one qutrit'

    def applied_to_trits(self, trits):
        return [(trits[0] * 2 + 1) % 3]


class Flip02Gate(raw_types.TernaryLogicGate,
                 ops.ReversibleEffect,
                 ops.TextDiagrammable):
    def inverse(self):
        return self

    def text_diagram_info(self, args):
        return ops.TextDiagramInfo(('[F02]',))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) == 1, 'Gate only operates on one qutrit'

    def applied_to_trits(self, trits):
        return [(trits[0] * 2 - 1) % 3]


class Flip12Gate(raw_types.TernaryLogicGate,
                 ops.ReversibleEffect,
                 ops.TextDiagrammable):
    def inverse(self):
        return self

    def text_diagram_info(self, args):
        return ops.TextDiagramInfo(('[F12]',))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) == 1, 'Gate only operates on one qutrit'

    def applied_to_trits(self, trits):
        return [(trits[0] * 2) % 3]


class SwapQubitsGate(raw_types.TernaryLogicGate,
                    ops.ReversibleEffect,
                    ops.CompositeGate,
                    ops.TextDiagrammable):
    def inverse(self):
        return self

    def text_diagram_info(self, args):
        return ops.TextDiagramInfo(('[Swap 01]','[Swap 01]'))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) == 2, 'Gate only operates on two qutrits'

    def applied_to_trits(self, trits):
        return [trits[1], trits[0]]

    def default_decompose(self, qubits):
        q0, q1 = qubits
        return (
            C1F01(q0, q1),
            C1F01(q1, q0),
            C1F01(q0, q1),
        )


class SwapGate(raw_types.TernaryLogicGate,
                    ops.ReversibleEffect,
                    ops.CompositeGate,
                    ops.TextDiagrammable):
    def inverse(self):
        return self

    def text_diagram_info(self, args):
        return ops.TextDiagramInfo(('[Swap 012]','[Swap 012]'))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) == 2, 'Gate only operates on two qutrits'

    def applied_to_trits(self, trits):
        return [trits[1], trits[0]]

    def default_decompose(self, qubits):
        q0, q1 = qubits
        return (
            # q1 += q0
            C1PlusOne(q0, q1),
            C2MinusOne(q0, q1),
            # q0 -= q1
            C1MinusOne(q1, q0),
            C2PlusOne(q1, q0),
            # q1 += q0
            C1PlusOne(q0, q1),
            C2MinusOne(q0, q1),
            # q0 = -q0
            F12(q0),
        )


# Create instances of gates
base_gates = {
    'PlusOne': PlusOneGate(),
    'MinusOne': MinusOneGate(),
    'F01': Flip01Gate(),
    'F02': Flip02Gate(),
    'F12': Flip12Gate(),
    'SwapQubits': SwapQubitsGate(),
    'Swap': SwapGate(),
}
vars().update(base_gates)


# Generate controlled gates
from cirq.qutrit.controlled_ternary_gate import ControlledTernaryGate
controlled_gates = {}
max_controls = 4
for name, gate in base_gates.items():
    controlled_gates.update(
        ControlledTernaryGate.all_controlled_gates(gate, name, max_controls))
vars().update(controlled_gates)
