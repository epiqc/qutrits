
from cirq import ops
from cirq.qutrit import raw_types
from cirq.qutrit import common_gates


class AncillaGenerationGate(raw_types.TernaryLogicGate,
                            ops.ReversibleEffect,
                            ops.CompositeGate,
                            ops.TextDiagrammable):
    _map = {
        (0,0,0): (0,0,0),
        (0,0,1): (0,2,0),
        (0,1,0): (0,1,0),
        (0,1,1): (1,2,0),
        (1,0,0): (1,0,0),
        (1,0,1): (2,1,0),
        (1,1,0): (1,1,0),
        (1,1,1): (2,2,0),
    }
    _inv_map = {v: k for k, v in _map.items()}
    assert len(_map) == len(_inv_map), '_map is not reversible'
    _all_map = dict(_map)
    _all_map.update(_inv_map)
    for k in _map:
        assert _map[k] == _all_map[k], '_map is invalid'

    def __init__(self, *, _inverted=False):
        self._inverted = _inverted

    def inverse(self):
        return AncillaGenerationGate(_inverted=not self._inverted)

    def text_diagram_info(self, args):
        if self._inverted:
            return ops.TextDiagramInfo(('0,1,2->0,1', '0,1,2->0,1', '0->0,1'))
        else:
            return ops.TextDiagramInfo(('0,1->0,1,2', '0,1->0,1,2', '0,1->0'))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) == 3, 'Gate only operates on three qutrits'

    def applied_to_trits(self, trits):
        trits = tuple(trits)
        return list(self._all_map.get(trits, trits))

    def default_decompose(self, qubits):
        q0, q1, q2 = qubits
        op_list = (
            common_gates.C1PlusOne(q2, q1),
            common_gates.C1PlusOne(q2, q0),

            common_gates.C1C1PlusOne(q0, q1, q2),
            common_gates.C2PlusOne(q2, q1),
            common_gates.C2MinusOne(q2, q0),

            common_gates.C0C2MinusOne(q0, q1, q2),
            common_gates.C1C1MinusOne(q0, q1, q2),
            common_gates.C01C01PlusOne(q0, q1, q2),
            common_gates.MinusOne(q2),
        )
        if self._inverted:
            return ops.inverse(op_list)
        else:
            return op_list


AncillaGen = AncillaGenerationGate()
