# Adversarial Threat Validity Checks

| Check | Passed | Detail |
|---|---:|---|
| causal_action_api_has_no_current_pattern | True | self,symbol_index,cfg,rng |
| causal_actions_are_historical_sets | True | all m>0 actions match an available historical set |
| causal_trajectory_reproducible | True | fresh explicit states and identical seeds produce identical trajectories |
| receiver_order_does_not_change_attack | True | collisions={'none': 108, 'mixllr': 108, 'oracle': 108} |
| delayed_feedback_not_used_early | True | D_f=2 report changes estimates only after two additional slots |
| systematic_sampler_has_fixed_size_without_duplicates | True | size=64, unique=64 |
| systematic_sampler_preserves_pash_marginals | True | max_abs_error=0.00800, target_max=0.15000 |
