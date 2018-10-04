
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


# Create instances of gates
base_gates = {
    'PlusOne': PlusOneGate(),
    'MinusOne': MinusOneGate(),
    'F01': Flip01Gate(),
    'F02': Flip02Gate(),
    'F12': Flip12Gate(),
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
