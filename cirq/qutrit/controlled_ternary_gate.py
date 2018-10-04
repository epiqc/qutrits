
import itertools

from cirq import ops
from cirq.qutrit import raw_types


class ControlledTernaryGate(raw_types.TernaryLogicGate,
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
