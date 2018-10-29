
import itertools

from cirq import ops, line, circuits, extension


def decompose_depth(*operations, d=1):
    if d <= 0:
        yield from operations
        return
    for op in ops.flatten_op_tree(operations):
        composite_op = extension.try_cast(ops.CompositeOperation, op)
        if composite_op is not None:
            yield from decompose_depth(composite_op.default_decompose(), d=d-1)
        else:
            yield op

def default_ternary_state(qubits):
    return {q:0 for q in qubits}

def evaluate_ternary_circuit(circuit, input_state=None):
    if input_state is None:
        input_state = default_ternary_state(circuit.all_qubits())
    else:
        state = input_state.copy()
    _evaluate_ternary_circuit(circuit.all_operations(), state)
    return state

def _evaluate_ternary_circuit(op_tree, state):
    for op in ops.flatten_op_tree(op_tree):
        if hasattr(op, 'apply_to_ternary_state'):
            op.apply_to_ternary_state(state)
        else:
            _evaluate_ternary_circuit(
                op.default_decompose(),
                state)

def trit_list_to_state(qubits, trit_values):
    state = default_ternary_state(qubits)
    state.update(zip(qubits, trit_values))
    return state

def verify_gate(gate, num_qubits, max_test_value=2**100, trinary_input=False, depth=1):
    qubits = line.LineQubit.range(num_qubits)
    op = gate(*qubits)
    verify_ops(op, max_test_value=max_test_value, trinary_input=trinary_input, depth=depth)
def verify_ops(*op_tree, max_test_value=2**100, trinary_input=False, depth=1):
    if trinary_input:
        raise NotImplementedError
        # TODO
    qubits = set()
    op_list = tuple(ops.flatten_op_tree(op_tree))
    for op in op_list:
        qubits.update(op.qubits)
    qubits = sorted(qubits)
    num_qubits = len(qubits)
    sub_ops = tuple(ops.flatten_op_tree(decompose_depth(op_list, d=depth)))
    for i in range(min(2**num_qubits, max_test_value)):
        bits = tuple(map(int, reversed('{:0{}b}'.format(i, num_qubits))))
        state = trit_list_to_state(qubits, bits)
        state2 = state.copy()
        # Apply gate directly
        for op in op_list:
            op.apply_to_ternary_state(state)
        # Apply gate decomposition
        for sub_op in sub_ops:
            sub_op.apply_to_ternary_state(state2)
        # Verify that the two agree
        if state != state2:
            input_state_str = ''.join(map(str, bits))
            output_state_str = ''.join(map(str, (state[q] for q in qubits)))
            output_state2_str = ''.join(map(str, (state2[q] for q in qubits)))
            raise RuntimeError(
                'Gate {!r} decomposition is invalid for input {}: {} != {}'.format(
                op_list, input_state_str, output_state_str, output_state2_str))

def verify_gate_inverse(gate, num_qubits, max_test_value=2**100):
    qubits = line.LineQubit.range(num_qubits)
    op = gate(*qubits)
    op_inv = op.inverse()
    for i in range(min(2**num_qubits, max_test_value)):
        bits = tuple(map(int, reversed('{:0{}b}'.format(i, num_qubits))))
        state = trit_list_to_state(qubits, bits)
        # Apply gate then inverse gate
        op.apply_to_ternary_state(state)
        op_inv.apply_to_ternary_state(state)
        # Verify that the state goes back to the initial state
        out_bits = tuple(state[q] for q in qubits)
        if out_bits != bits:
            input_state_str = ''.join(map(str, bits))
            output_state_str = ''.join(map(str, out_bits))
            raise RuntimeError(
                'Gate {!r} inverse is invalid for input {} != {}'.format(
                gate, input_state_str, output_state_str))

def verify_decomposition_inverse(*op_tree, max_test_value=2**100, depth=1):
    qubits = set()
    op_list = tuple(ops.flatten_op_tree(op_tree))
    for op in op_list:
        qubits.update(op.qubits)
    qubits = sorted(qubits)
    num_qubits = len(qubits)
    sub_ops = tuple(ops.flatten_op_tree(decompose_depth(op_list, d=depth)))
    sub_ops_inv = tuple(ops.flatten_op_tree(decompose_depth(ops.inverse(op_list), d=depth)))

    for trits in itertools.product((0,1,2), repeat=num_qubits):
        state = trit_list_to_state(qubits, trits)
        state_orig = state.copy()
        for op in sub_ops:
            op.apply_to_ternary_state(state)
        for op in sub_ops_inv:
            op.apply_to_ternary_state(state)
        if state != state_orig:
            input_state_str = ''.join(map(str, trits))
            output_state_str = ''.join(map(str, (state[q] for q in qubits)))
            raise RuntimeError(
                'Gate {!r} inverse is invalid for input {} != {}'.format(
                op_list, input_state_str, output_state_str))
