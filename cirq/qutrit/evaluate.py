
from cirq import ops, line, circuits
#from cirq.qutrit


def default_ternary_state(qubits):
    return {q:0 for q in qubits}

def evaluate_ternary_circuit(circuit, input_state=None):
    if input_state is None:
        input_state = default_ternary_state(circuit.all_qubits())
    else:
        state = input_state.copy()
    _evaluate_ternary_circuit(circuit.all_operations(), state)
    return state

def _evaluate_ternary_circuit(ops, state):
    for op in ops:
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

def verify_gate(gate, num_qubits, max_test_value=2**14):
    qubits = line.LineQubit.range(num_qubits)
    op = gate(*qubits)
    sub_ops = tuple(ops.flatten_op_tree(op.default_decompose()))
    for i in range(min(2**num_qubits, max_test_value)):
        bits = tuple(map(int, reversed('{:0{}b}'.format(i, num_qubits))))
        state = trit_list_to_state(qubits, bits)
        state2 = state.copy()
        # Apply gate directly
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
                gate, input_state_str, output_state_str, output_state2_str))

def verify_gate_inverse(gate, num_qubits, max_test_value=2**14):
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


