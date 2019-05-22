
import itertools

from cirq import ops
from cirq.qutrit import raw_types, common_gates, small_plus_k_carry
from cirq.qutrit.ancilla_generation_gate import AncillaGen


def bits_to_val(bits):
    if len(bits) == 0: return 0
    return int(''.join(map('{:d}'.format, reversed(bits))), 2)

def val_to_bits(val, num_bits):
    val &= ~((-1) << num_bits)
    return tuple(map(int, reversed('{:0{}b}'.format(val, num_bits))))


class PlusKGate(raw_types.TernaryLogicGate,
                ops.ReversibleEffect,
                ops.CompositeGate,
                ops.TextDiagrammable):
    def __init__(self, k, *, _inverted=False):
        self.k = k
        self._inverted = _inverted

    def inverse(self):
        return PlusKGate(k=self.k, _inverted=not self._inverted)

    def text_diagram_info(self, args):
        syms = ['[{} k_{}={}]'.format(
                    'Minus' if self._inverted else 'Plus', i, bit)
                for i, bit in enumerate(self.k)]
        return ops.TextDiagramInfo(tuple(syms))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) == len(self.k), 'Gate only operates on len(k) qutrits'

    def applied_to_trits(self, trits):
        k_val = bits_to_val(self.k)
        reg_val = bits_to_val(trits)
        reg_val += -k_val if self._inverted else k_val
        return val_to_bits(reg_val, len(trits))

    def default_decompose(self, qubits):
        k = self.k
        if self._inverted:
            k = val_to_bits(-bits_to_val(k), len(k))

        yield from self._gen_all_carry(qubits, k, forward=True)
        yield from self._gen_all_carry(qubits, k, forward=False)

        if self.k[0]:
            yield common_gates.F01(qubits[0])

    @classmethod
    def _gen_all_carry(cls, qubits, k, carry_in=False, carry_ancilla=None, forward=True):
        if len(qubits) <= 0: return
        elif len(qubits) == 1:
            return#yield common_gates.PlusOne(qubits[0])
        elif len(qubits) == 2:
            if forward:
                if not k[0]:
                    yield common_gates.C2F01(qubits[0], qubits[1])
                else:
                    yield common_gates.C12F01(qubits[0], qubits[1])
                if k[1]:
                    yield common_gates.F01(qubits[1])
        else:
            half = len(qubits) // 2
            half_half = half // 2
            plenty_of_space = half - half_half - 1 >= 3
            gen_op = None
            new_ancilla = None
            if plenty_of_space:
                gen_op = AncillaGen(*qubits[half-3:half])
                new_ancilla = qubits[half-1]
                next_carry_ancilla = carry_ancilla
            else:
                next_carry_ancilla = None
            pre_qubits = () if carry_ancilla is None else (carry_ancilla,)
            if forward:
                yield PlusKCarryGate(k[:half], carry_in, carry_ancilla is not None)(
                                *pre_qubits, *qubits[:half+1])
            if not forward:
                yield from cls._gen_all_carry(qubits[:half], k[:half], carry_in, next_carry_ancilla, forward)
            if gen_op is not None:
                yield gen_op
            yield from cls._gen_all_carry(qubits[half:], k[half:], True, new_ancilla, forward)
            if gen_op is not None:
                yield gen_op.inverse()
            if forward:
                yield from cls._gen_all_carry(qubits[:half], k[:half], carry_in, next_carry_ancilla, forward)
            if not forward:
                yield PlusKUncarryAddGate(k[:half], carry_in, carry_ancilla is not None)(
                                *pre_qubits, *qubits[:half+1])
                if k[half]:
                    yield common_gates.F01(qubits[half])


class PlusKCarryGate(raw_types.TernaryLogicGate,
                     ops.ReversibleEffect,
                     ops.CompositeGate,
                     ops.TextDiagrammable):
    def __init__(self, k, carry_in=False, top_ancilla=False, *, _inverted=False):
        self.k = k
        self.carry_in = carry_in
        self.top_ancilla = top_ancilla
        self._inverted = _inverted

    def inverse(self):
        return PlusKCarryGate(self.k, carry_in=self.carry_in,
                              top_ancilla=self.top_ancilla,
                              _inverted=not self._inverted)

    def text_diagram_info(self, args):
        syms = ['[{}Carry k_{}={}]'.format(
                    '->'*(i==0 and self.carry_in), i, int(bit))
                for i, bit in enumerate(self.k)]
        syms.append('[-1]' if self._inverted else '[+1]')
        if self.top_ancilla:
            syms[:0] = ['[Ancilla]']
        return ops.TextDiagramInfo(tuple(syms))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) == len(self.k)+1+self.top_ancilla, (
               'Gate only operates on len(k)+1 qutrits')

    def applied_to_trits(self, trits):
        anc_trits = []
        if self.top_ancilla:
            anc_trits = [trits[0]]
            trits[:1] = []

        k_val = bits_to_val(self.k)
        if self.carry_in:
            reg_val = bits_to_val(trits[1:-1]) << 1
            k_val |= 1
            reg_val |= trits[0] == 2 or (trits[0] == 1 and self.k[0])
        else:
            reg_val = bits_to_val(trits[:-1])
        if (k_val + reg_val).bit_length() > len(self.k):
            trits[-1] = (trits[-1] + 1 + self._inverted) % 3
        return anc_trits + trits

    def default_decompose(self, qubits):
        if self._inverted:
            cont_gate = common_gates.MinusOne
        else:
            cont_gate = common_gates.PlusOne
        if self.top_ancilla:
            carry_ancilla, qubits = qubits[0], qubits[1:]
        else:
            carry_ancilla = None
        return _gen_or_and_control_u(cont_gate, qubits, self.k, self.carry_in, carry_ancilla)


class PlusKUncarryAddGate(raw_types.TernaryLogicGate,
                          ops.ReversibleEffect,
                          ops.CompositeGate,
                          ops.TextDiagrammable):
    def __init__(self, k, carry_in=False, top_ancilla=False):
        self.k = k
        self.carry_in = carry_in
        self.top_ancilla = top_ancilla

    def inverse(self):
        return self

    def text_diagram_info(self, args):
        syms = ['[{}Uncarry Add k_{}={}]'.format(
                    '->'*(i==0 and self.carry_in), i, int(bit))
                for i, bit in enumerate(self.k)]
        syms.append('[F02]')
        if self.top_ancilla:
            syms[:0] = ['[Ancilla]']
        return ops.TextDiagramInfo(tuple(syms))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) == len(self.k)+1+self.top_ancilla, (
               'Gate only operates on len(k)+1 qutrits')

    def applied_to_trits(self, trits):
        anc_trits = []
        if self.top_ancilla:
            anc_trits = [trits[0]]
            trits[:1] = []

        k_val = bits_to_val(self.k)
        if self.carry_in:
            reg_val = bits_to_val(trits[1:-1]) << 1
            k_val |= 1
            reg_val |= trits[0] == 2 or (trits[0] == 1 and self.k[0])
        else:
            reg_val = bits_to_val(trits[:-1])
        reg_val ^= ~(~0 << (len(trits)-2)) << 1  # Invert controls except first
        if (k_val + reg_val).bit_length() > len(self.k):
            trits[-1] = (trits[-1] * 2 - 1) % 3
        return anc_trits + trits

    def default_decompose(self, qubits):
        if self.top_ancilla:
            carry_ancilla, qubits = qubits[0], qubits[1:]
        else:
            carry_ancilla = None
        cont_gate = common_gates.F02
        not_ops = [common_gates.F01(q) for q in qubits[1:-1]]
        yield from not_ops
        yield from _gen_or_and_control_u(cont_gate, qubits, self.k, self.carry_in, carry_ancilla)
        yield from not_ops


def _gen_or_and_control_u(u_gate, qubits, k, carry_in=False, carry_ancilla=None):
    if not carry_in and not any(k):
        # No carry and k=0000...
        return

    if _can_make_enough_ancilla(k, carry_in=carry_in, carry_ancilla=carry_ancilla):
        forward_ops = tuple(_gen_or_and_forward(qubits[:-1], k, carry_in, carry_ancilla))
        yield from forward_ops
        yield common_gates.ControlledTernaryGate(u_gate, ((0,1),))(
                                qubits[-2], qubits[-1])
        yield from ops.inverse(forward_ops)
    else:
        yield small_plus_k_carry.SmallPlusKCarry(k, carry_in, u_gate)(*qubits)


def _can_make_enough_ancilla(k, carry_in=False, carry_ancilla=None):
    if carry_in and carry_ancilla is None:
        return False
    if carry_in and not k[0]:
        k = list(k)
        k[0] = True

    one_group = 0
    free_count = 0
    input_count = 0
    last_zero_k_i = max((-k_i, i) for i, k_i in enumerate(k))[1]
    if k[last_zero_k_i]: last_zero_k_i = -1
    for k_i in k[:last_zero_k_i+1]:
        if k_i:
            one_group += 1
        elif one_group > 0:
            if one_group > 5:
                free_count += one_group - 5
            if one_group <= 3:
                input_count += 1
            one_group = 0

        if not k_i:
            free_count += 1
    n_trailing_ones = len(k) - (last_zero_k_i+1)
    if n_trailing_ones > 1:
        input_count += 1
        free_count += n_trailing_ones - 1
    ancilla_count = free_count // 3

    if ancilla_count == 0:
        return input_count == 0
    return (input_count + ancilla_count - 1) // ancilla_count <= 4


def _gen_or_and_forward(qubits, k, carry_in=False, carry_ancilla=None):
    if carry_in:
        print('Carrying in!')
        assert carry_ancilla is not None, 'Carry in but no carry ancilla provided'

        cont = (1, 2) if k[0] else (2,)
        yield common_gates.ControlledTernaryGate(common_gates.F01, (cont,)
                                )(qubits[0], carry_ancilla)

        if not k[0]:
            k = list(k)
            k[0] = True

        # Now use the ancilla as if it is the first qubit of the sum
        orig_qubit0 = qubits[0]
        qubits = list(qubits)
        qubits[0] = carry_ancilla

    # Layer 0: Compute if each zero bit can propagate to the end
    zero_qubits = tuple(q for k_i, q in zip(k, qubits) if not k_i)
    if len(zero_qubits) > 0:
        upward_and = UpwardMultiAndGate()(*zero_qubits)
        yield upward_and
    else:
        upward_and = None

    # Layer 1 (and plan layer 2): Calculate if each group of ones can generate
    # then propagate to the end
    one_qubit_group = []
    free_qubit_group = []  # For layer 2 planning
    new_ancilla_qubits = []  # Zero ancilla for layer 3
    gen_ancilla_ops = []  # Layer 2 operations
    layer3_qubits = []  #  Input calculate and store in ancilla for layer 3
    layer4_qubits = []  # 0/1 qubits to calculate the and of layer 3 for layer 4
    last_zero_k_i = max((-k_i, i) for i, k_i in enumerate(k))[1]
    if k[last_zero_k_i]: last_zero_k_i = -1
    for k_i, q in zip(k[:last_zero_k_i+1], qubits):
        if k_i:
            one_qubit_group.append(q)
            if len(one_qubit_group) >= 5:
                free_qubit_group.append(one_qubit_group[-5])  # Plan layer 2
        elif len(one_qubit_group) > 0:
            yield MultiOrAndGate()(*one_qubit_group, q)
            if len(one_qubit_group) > 3:
                yield common_gates.F01(one_qubit_group[-1])
                layer4_qubits.append(one_qubit_group[-1])
            else:
                layer3_qubits.append(one_qubit_group[-1])

            one_qubit_group.clear()

        # Plan layer 2
        if not k_i:
            free_qubit_group.append(q)
        while len(free_qubit_group) >= 3:
            gen_ancilla_ops.append(AncillaGen(*free_qubit_group[:3]))
            new_ancilla_qubits.append(free_qubit_group[2])
            layer4_qubits.append(free_qubit_group[2])
            free_qubit_group[:3] = ()

    trailing_one_qubits = qubits[last_zero_k_i+1:len(k)]
    last_layer_3_invert = False
    if len(trailing_one_qubits) == 1:
        yield common_gates.F01(trailing_one_qubits[0])
        layer4_qubits.append(trailing_one_qubits[0])
    elif len(trailing_one_qubits) > 1:
        yield from (common_gates.F01(q) for q in trailing_one_qubits)
        yield UpwardMultiControlPlusOneGate()(*trailing_one_qubits[::-1])
        free_qubit_group.extend(trailing_one_qubits[:-1])
        while len(free_qubit_group) >= 3:
            gen_ancilla_ops.append(AncillaGen(*free_qubit_group[:3]))
            new_ancilla_qubits.append(free_qubit_group[2])
            layer4_qubits.append(free_qubit_group[2])
            free_qubit_group[:3] = ()
        layer3_qubits.append(trailing_one_qubits[-1])
        last_layer_3_invert = True

    # Uncompute layer 0: Restore zero bits to the qubit basis
    if upward_and is not None:
        yield upward_and.inverse()

    # Layer 2: Generate ancilla for layer 3
    yield from gen_ancilla_ops

    # Layer 3: Collect information from qutrits into ancilla
    if len(new_ancilla_qubits) > 0:
        n_control = (len(layer3_qubits) + len(new_ancilla_qubits) - 1) // len(new_ancilla_qubits)
        assert n_control <= 4, 'Too few ancilla in layer 3'
        n_in = len(layer3_qubits)
        for n_anc in range(len(new_ancilla_qubits), 0, -1):
            n_control = n_in // n_anc
            controls = [(0,1),]*n_control
            if n_control == n_in and last_layer_3_invert:
                # Invert the control on the last layer 3 qubit
                controls[-1] = (2,)
            end = -n_in+n_control
            if end == 0: end = None
            yield common_gates.ControlledTernaryGate(
                        common_gates.F01, controls
                    )(*layer3_qubits[-n_in:end], new_ancilla_qubits[-n_anc])
            n_in -= n_control
        assert n_in == 0, 'Logic error'
    else:
        assert len(layer3_qubits) == 0, 'No ancilla in layer 3'

    # Layer 4: Collect carry answer into one qubit
    assert len(layer4_qubits) > 0, 'No qubits in layer 4'
    yield UpwardMultiControlPlusOneGate()(*layer4_qubits[::-1])

    # Make the last qubit the output
    if layer4_qubits[-1] != qubits[-1]:
        yield common_gates.Swap(layer4_qubits[-1], qubits[-1])


class UpwardMultiAndGate(raw_types.TernaryLogicGate,
                         ops.ReversibleEffect,
                         ops.CompositeGate,
                         ops.TextDiagrammable):
    def __init__(self, *, _inverted=False):
        self._inverted = _inverted

    def inverse(self):
        return UpwardMultiAndGate(_inverted=not self._inverted)

    def text_diagram_info(self, args):
        return ops.TextDiagramInfo(('[Upward and{}]'.format(
                                     ' inv' if self._inverted else ''),)
                                   * args.known_qubit_count)

    def validate_trits(self, trits):
        super().validate_trits(trits)

    def applied_to_trits(self, trits):
        inv = -1 if self._inverted else 1
        return [(trit + inv*all(t==1+self._inverted for t in trits[i+1:])) % 3
                for i, trit in enumerate(trits)]

    def default_decompose(self, qubits):
        if self._inverted:
            op_list = tuple(self.decompose_forward(qubits))
            return ops.inverse(op_list)
        else:
            return self.decompose_forward(qubits)

    def decompose_forward(self, qubits):
        n = len(qubits)
        for shift in range(((n-1).bit_length() - 1), -1, -1):
            num_controls = 1 << shift
            for i in range(n, num_controls, -num_controls*2):
                yield UpwardMultiControlPlusOneGate(bottom_control_2 = i!=n)(
                            *qubits[i-num_controls-1:i])
        if n > 0:
            yield common_gates.PlusOne(qubits[-1])


class UpwardMultiControlPlusOneGate(raw_types.TernaryLogicGate,
                                    ops.ReversibleEffect,
                                    ops.CompositeGate,
                                    ops.TextDiagrammable):
    def __init__(self, bottom_control_2=False, *, _inverted=False):
        self.bottom_control_2 = bottom_control_2
        self._inverted = _inverted

    def inverse(self):
        return UpwardMultiControlPlusOneGate(bottom_control_2=self.bottom_control_2,
                                             _inverted=not self._inverted)

    def text_diagram_info(self, args):
        syms = ['1'] * args.known_qubit_count
        syms[0] = '[-1]' if self._inverted else '[+1]'
        if self.bottom_control_2 and args.known_qubit_count > 1:
            syms[-1] = '2'
        return ops.TextDiagramInfo(tuple(syms))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) > 0, 'Gate only operates on one or more qutrits'

    def applied_to_trits(self, trits):
        control_triggered = (all(trit == 1 for trit in trits[1:-1]) and
                             all(trit == 1 + bool(self.bottom_control_2)
                                 for trit in trits[-1:]))
        if control_triggered:
            shift = -1 if self._inverted else 1
            trits[0] = (trits[0] + shift) % 3
        return trits

    def default_decompose(self, qubits):
        qubit_mask = {q: True for q in qubits}
        qubit_mask[qubits[-1]] = not self.bottom_control_2
        and_ops = tuple(_gen_log_and_upward(qubits, qubit_mask))
        if len(and_ops) <= 0:
            and_ops = (common_gates.PlusOne(qubits[0]),)
        if self._inverted:
            yield from and_ops[:-1]
            yield from ops.inverse(and_ops)
        else:
            yield from and_ops
            yield from ops.inverse(and_ops[:-1])


class MultiOrAndGate(raw_types.TernaryLogicGate,
                     ops.ReversibleEffect,
                     ops.CompositeGate,
                     ops.TextDiagrammable):
    """ Calculates ((q[0] or q[1] or ... or q[n-2]) and q[n-1]) and stores the
        result in q[n-2].

        If n <= 4, the ternary value 2 is stored in q[n-2]
        otherwise, the binary value 1 is stored in q[n-2].

        The value in q[n-1] is never changed but q[n-5:n-2] are used to store
        temporary results.
    """
    def __init__(self, last_true_val=2, *, _inverted=False):
        self.last_true_val = last_true_val
        self._inverted = _inverted

    def inverse(self):
        return MultiOrAndGate(_inverted=not self._inverted)

    def text_diagram_info(self, args):
        n = args.known_qubit_count
        if self._inverted:
            syms = ['[--Or inv-]'] * (n-5)
            syms.extend(['[  Or inv-]'] * ((n-2) - max(0, n-5)))
            syms.append('[>{}Or inv-]'.format('2' if n <= 4 else ' '))
            syms.append('[-And inv{}-]'.format(self.last_true_val if self.last_true_val!=1 else ''))
        else:
            syms = ['[-Or--]'] * (n-5)
            syms.extend(['[-Or  ]'] * ((n-2) - max(0, n-5)))
            syms.append('[-Or{}<]'.format('2' if n <= 4 else ' '))
            syms.append('[-{}And-]'.format(self.last_true_val if self.last_true_val!=1 else ''))
        return ops.TextDiagramInfo(tuple(syms))

    def validate_trits(self, trits):
        super().validate_trits(trits)
        assert len(trits) >= 2, 'Gate only operates on 2 or more qutrits'

    def applied_to_trits(self, trits):
        if self._inverted:
            result = trits[-2] == (1 if len(trits) >= 5 else 2)
            if len(trits) >= 5:
                trits[-3], trits[-2] = trits[-2], trits[-3]
                trits[-5:-2] = AncillaGen.inverse().applied_to_trits(trits[-5:-2])
                trits[-2] = (trits[-2] - all(trit==0 for trit in trits[:-2])) % 3
                trits[-2] = (trits[-2] * 2 + 1) % 3
            elif len(trits) == 4:
                trits[2] = (trits[2] - (trits[1] == 2)) % 3
                trits[2] = (trits[2] - (trits[0] == 2)) % 3
                trits[0] = (trits[0] + (trits[1] == 2)) % 3
                trits[1] = (trits[1] + (trits[2] == 2)) % 3
                trits[0] = (trits[0] + (trits[2] == 2)) % 3
                trits[2] = (trits[2] - (trits[3] == self.last_true_val)) % 3
                trits[1] = (trits[1] - (trits[3] == self.last_true_val)) % 3
                trits[0] = (trits[0] - (trits[3] == self.last_true_val)) % 3
            elif len(trits) == 3:
                trits[1] = (trits[1] - (trits[0] == 2)) % 3
                trits[0] = (trits[0] + (trits[1] == 2)) % 3
                trits[1] = (trits[1] - (trits[2] == self.last_true_val)) % 3
                trits[0] = (trits[0] - (trits[2] == self.last_true_val)) % 3
            elif len(trits) == 2:
                trits[-2] = (trits[-2] - (trits[-1] == self.last_true_val)) % 3
        else:
            result = any(trit == 1 for trit in trits[:-1]) and trits[-1] == 1
            if len(trits) >= 5:
                trits[-2] = (trits[-2] * 2 + 1) % 3
                trits[-2] = (trits[-2] + all(trit==0 for trit in trits[:-2])) % 3
                trits[-5:-2] = AncillaGen.applied_to_trits(trits[-5:-2])
                trits[-3] = int(result)
                trits[-3], trits[-2] = trits[-2], trits[-3]
                assert (trits[-2] == 1) == result, 'Internal logic error'
            elif len(trits) == 4:
                trits[0] = (trits[0] + (trits[3] == self.last_true_val)) % 3
                trits[1] = (trits[1] + (trits[3] == self.last_true_val)) % 3
                trits[2] = (trits[2] + (trits[3] == self.last_true_val)) % 3
                trits[0] = (trits[0] - (trits[2] == 2)) % 3
                trits[1] = (trits[1] - (trits[2] == 2)) % 3
                trits[0] = (trits[0] - (trits[1] == 2)) % 3
                trits[2] = (trits[2] + (trits[0] == 2)) % 3
                trits[2] = (trits[2] + (trits[1] == 2)) % 3
                assert (trits[-2] == 2) == result, 'Internal logic error'
            elif len(trits) == 3:
                trits[0] = (trits[0] + (trits[2] == self.last_true_val)) % 3
                trits[1] = (trits[1] + (trits[2] == self.last_true_val)) % 3
                trits[0] = (trits[0] - (trits[1] == 2)) % 3
                trits[1] = (trits[1] + (trits[0] == 2)) % 3
                assert (trits[-2] == 2) == result, 'Internal logic error'
            elif len(trits) == 2:
                trits[-2] = (trits[-2] + (trits[-1] == self.last_true_val)) % 3
                assert (trits[-2] == 2) == result, 'Internal logic error'
        return trits

    def default_decompose(self, qubits):
        if self._inverted:
            op_list = tuple(self.decompose_forward(qubits))
            return ops.inverse(op_list)
        else:
            return self.decompose_forward(qubits)

    def decompose_forward(self, qubits):
        return {2: self.decompose_2,
                3: self.decompose_3,
                4: self.decompose_4}.get(len(qubits),
                   self.decompose_large)(qubits)

    def decompose_2(self, qubits):
        return (
            common_gates.ControlledTernaryGate(common_gates.PlusOne,
                                               ((self.last_true_val,),))(
                                    qubits[1], qubits[0]),
        )

    def decompose_3(self, qubits):
        return (
            common_gates.ControlledTernaryGate(common_gates.PlusOne,
                                               ((self.last_true_val,),))(
                                    qubits[2], qubits[0]),
            common_gates.ControlledTernaryGate(common_gates.PlusOne,
                                               ((self.last_true_val,),))(
                                    qubits[2], qubits[1]),
            common_gates.C2MinusOne(qubits[1], qubits[0]),
            common_gates.C2PlusOne(qubits[0], qubits[1]),
        )

    def decompose_4(self, qubits):
        return (
            common_gates.ControlledTernaryGate(common_gates.PlusOne,
                                               ((self.last_true_val,),))(
                                    qubits[3], qubits[0]),
            common_gates.ControlledTernaryGate(common_gates.PlusOne,
                                               ((self.last_true_val,),))(
                                    qubits[3], qubits[1]),
            common_gates.ControlledTernaryGate(common_gates.PlusOne,
                                               ((self.last_true_val,),))(
                                    qubits[3], qubits[2]),
            common_gates.C2MinusOne(qubits[2], qubits[0]),
            common_gates.C2MinusOne(qubits[2], qubits[1]),
            common_gates.C2MinusOne(qubits[1], qubits[0]),
            common_gates.C2PlusOne(qubits[0], qubits[2]),
            common_gates.C2PlusOne(qubits[1], qubits[2]),
        )

    def decompose_large(self, qubits):
        flip_ops = tuple(common_gates.F01(q) for q in qubits[:-1])
        yield from flip_ops
        and_ops = tuple(_gen_log_and_upward(qubits[:-1][::-1]))
        yield and_ops
        yield ops.inverse(and_ops[:-1])  # Uncompute, some of the uncompute
                                         # is optional
        yield from flip_ops[:-1]  # Optional
        yield AncillaGen(*qubits[-5:-2])
        yield common_gates.Swap(qubits[-2], qubits[-3])
        yield common_gates.ControlledTernaryGate(common_gates.PlusOne,
                                                 ((self.last_true_val,),
                                                  (0,1)))(
                                    qubits[-1], qubits[-3], qubits[-2])


def _gen_log_and_upward(qubits, qubit_mask=None):
    if qubit_mask is None:
        qubit_mask = {q: True for q in qubits}
    n = len(qubits)
    if n == 0: return
    elif n == 1: return
    elif n == 2:
        assert qubit_mask[qubits[0]]
        qubit_mask[qubits[0]] = False
        yield common_gates.ControlledTernaryGate(common_gates.PlusOne,
                            ((1 if qubit_mask[qubits[1]] else 2,),))(
                        qubits[1], qubits[0])
    else:
        nice_n = (1 << (n.bit_length() - 1)) - 1
        yield from _gen_log_and_upward(qubits[1:-nice_n], qubit_mask)
        if nice_n + 1 <= n:
            yield from _gen_log_and_upward(qubits[-nice_n:], qubit_mask)
        assert qubit_mask[qubits[0]]
        qubit_mask[qubits[0]] = False
        if nice_n + 1 == n:
            yield common_gates.ControlledTernaryGate(common_gates.PlusOne,
                                ((1 if qubit_mask[qubits[-nice_n]] else 2,),))(
                            qubits[-nice_n], qubits[0])
        else:
            yield common_gates.ControlledTernaryGate(common_gates.PlusOne,
                                ((1 if qubit_mask[qubits[1]] else 2,),
                                 (1 if qubit_mask[qubits[-nice_n]] else 2,)))(
                            qubits[1], qubits[-nice_n], qubits[0])
