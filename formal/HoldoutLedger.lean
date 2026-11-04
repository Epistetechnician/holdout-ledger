/-!
# Holdout ledger: the combinatorial core

Level 1 formal evidence, in the repo's own ladder. What is proved here, with no `sorry` and no axioms beyond Lean's standard
`propext`, `Classical.choice` and `Quot.sound` (checked with `#print axioms`):

* `length_transcripts`: the number of verdict transcripts a gate can emit is the product of its alphabet sizes.
* `realized_mem`: whatever an adaptive proposer does, the transcript it actually sees is one of them.
* `count_any_le`: a counting-measure union bound over a finite family of events.
* `adaptive_union_bound`: the probability that the output of an adaptive loop is *bad* is at most
  (number of transcripts) x (worst per-hypothesis failure count). This is the information route.
* `occam_union_bound`: the same with the candidate list indexed by programs. This is the description route.
* `cert_antitone`, `cert_ledger_ge_info`, `cert_ledger_ge_desc`: billing more bits never raises a claim,
  and charging the cheaper route never certifies less than either route alone.

What is NOT proved: the per-hypothesis concentration inequality (Hoeffding / empirical Bernstein). It enters
as the hypothesis `hconc`. The sample space is a finite list under the counting measure, not a measure space.
Nothing here concerns the Rust or Python code that implements the ledger.
-/

namespace HoldoutLedger

/-- Every verdict transcript of `T` rounds when round `t` can return any of `size t` verdicts. -/
def transcripts (size : Nat → Nat) : Nat → List (List Nat)
  | 0 => [[]]
  | t + 1 => (transcripts size t).flatMap fun vs => (List.range (size t)).map fun v => vs ++ [v]

/-- Product of the alphabet sizes of the first `T` rounds. -/
def count (size : Nat → Nat) : Nat → Nat
  | 0 => 1
  | t + 1 => count size t * size t

theorem sum_map_const {α : Type} (l : List α) (k : Nat) : (l.map fun _ => k).sum = l.length * k := by
  induction l with
  | nil => simp
  | cons a l ih => simp [ih, Nat.succ_mul, Nat.add_comm]

theorem length_transcripts (size : Nat → Nat) (T : Nat) :
    (transcripts size T).length = count size T := by
  induction T with
  | zero => rfl
  | succ t ih =>
    simp only [transcripts, count, List.length_flatMap, List.length_map, List.length_range]
    rw [sum_map_const, ih]

/-- Verdicts seen after `t` rounds of a deterministic proposer `prop` (it maps the verdicts so far to its next
hypothesis) facing outcome `ω` through `gate ω t h`, the verdict for hypothesis `h` in round `t`. -/
def realized {Ω : Type} (prop : List Nat → Nat) (gate : Ω → Nat → Nat → Nat) (ω : Ω) : Nat → List Nat
  | 0 => []
  | t + 1 => realized prop gate ω t ++ [gate ω t (prop (realized prop gate ω t))]

theorem realized_mem {Ω : Type} (size : Nat → Nat) (prop : List Nat → Nat) (gate : Ω → Nat → Nat → Nat)
    (hv : ∀ ω t h, gate ω t h < size t) (ω : Ω) (T : Nat) :
    realized prop gate ω T ∈ transcripts size T := by
  induction T with
  | zero => simp [realized, transcripts]
  | succ t ih =>
    simp only [realized, transcripts, List.mem_flatMap, List.mem_map, List.mem_range]
    exact ⟨realized prop gate ω t, ih, gate ω t (prop (realized prop gate ω t)), hv ω t _, rfl⟩

/-- Counting-measure union bound: the outcomes on which some candidate is bad. -/
theorem count_any_le {α β : Type} (Ω : List α) (cands : List β) (bad : β → α → Bool) :
    Ω.countP (fun ω => cands.any fun g => bad g ω) ≤ (cands.map fun g => Ω.countP (bad g)).sum := by
  induction cands with
  | nil => simp
  | cons g gs ih =>
    have key : ∀ (l : List α) (p q : α → Bool),
        l.countP (fun ω => p ω || q ω) ≤ l.countP p + l.countP q := by
      intro l p q
      induction l with
      | nil => simp
      | cons a l ihl =>
        by_cases hp : p a = true <;> by_cases hq : q a = true <;>
          simp [hp, hq] <;> omega
    have := key Ω (bad g) (fun ω => gs.any fun g' => bad g' ω)
    simp only [List.any_cons, List.map_cons, List.sum_cons]
    omega

theorem sum_le_length_mul {β : Type} (l : List β) (f : β → Nat) (p : Nat) (h : ∀ x ∈ l, f x ≤ p) :
    (l.map f).sum ≤ l.length * p := by
  induction l with
  | nil => simp
  | cons a l ih =>
    simp only [List.map_cons, List.sum_cons, List.length_cons, Nat.succ_mul]
    have h1 := h a (by simp)
    have h2 := ih (fun x hx => h x (by simp [hx]))
    omega

/-- Information route. An adaptive loop reads `T` verdicts. If every transcript-indexed hypothesis fails on at
most `p` outcomes, the hypothesis the loop outputs fails on at most `count size T * p` outcomes. -/
theorem adaptive_union_bound {Ω : Type} (Ωs : List Ω) (size : Nat → Nat) (T : Nat)
    (prop : List Nat → Nat) (gate : Ω → Nat → Nat → Nat) (hv : ∀ ω t h, gate ω t h < size t)
    (bad : Nat → Ω → Bool) (p : Nat)
    (hconc : ∀ g ∈ (transcripts size T).map prop, Ωs.countP (bad g) ≤ p) :
    Ωs.countP (fun ω => bad (prop (realized prop gate ω T)) ω) ≤ count size T * p := by
  let cands := (transcripts size T).map prop
  have hsub : Ωs.countP (fun ω => bad (prop (realized prop gate ω T)) ω)
      ≤ Ωs.countP (fun ω => cands.any fun g => bad g ω) := by
    apply List.countP_mono_left
    intro ω _ hb
    simp only [List.any_eq_true, cands, List.mem_map]
    exact ⟨prop (realized prop gate ω T), ⟨realized prop gate ω T, realized_mem size prop gate hv ω T, rfl⟩, hb⟩
  have h2 := count_any_le Ωs cands bad
  have h3 := sum_le_length_mul cands (fun g => Ωs.countP (bad g)) p hconc
  have hl : cands.length = count size T := by simp [cands, length_transcripts]
  rw [hl] at h3
  omega

/-- Description route. If a fixed finite list of candidate hypotheses contains the output on every outcome,
the output fails on at most `cands.length * p` outcomes, however many queries were made. -/
theorem occam_union_bound {Ω : Type} (Ωs : List Ω) (cands : List Nat) (out : Ω → Nat) (bad : Nat → Ω → Bool)
    (p : Nat) (hmem : ∀ ω, out ω ∈ cands) (hconc : ∀ g ∈ cands, Ωs.countP (bad g) ≤ p) :
    Ωs.countP (fun ω => bad (out ω) ω) ≤ cands.length * p := by
  have hsub : Ωs.countP (fun ω => bad (out ω) ω) ≤ Ωs.countP (fun ω => cands.any fun g => bad g ω) := by
    apply List.countP_mono_left
    intro ω _ hb
    simp only [List.any_eq_true]
    exact ⟨out ω, hmem ω, hb⟩
  have h2 := count_any_le Ωs cands bad
  have h3 := sum_le_length_mul cands (fun g => Ωs.countP (bad g)) p hconc
  omega

/-! ### Claim ceilings are monotone in billed bits -/

/-- A certified lower bound: observed gain minus a radius that depends on the bits billed. -/
def cert (rad : Nat → Int) (dhat : Int) (bits : Nat) : Int := dhat - rad bits

theorem cert_antitone (rad : Nat → Int) (hm : ∀ a b : Nat, a ≤ b → rad a ≤ rad b) (dhat : Int) {a b : Nat}
    (hab : a ≤ b) : cert rad dhat b ≤ cert rad dhat a := by
  unfold cert
  have := hm _ _ hab
  omega

/-- Charging the cheaper of the two routes never certifies less than either route alone. -/
theorem cert_ledger_ge_info (rad : Nat → Int) (hm : ∀ a b : Nat, a ≤ b → rad a ≤ rad b) (dhat : Int)
    (info desc : Nat) :
    cert rad dhat info ≤ cert rad dhat (min info desc) :=
  cert_antitone rad hm dhat (Nat.min_le_left _ _)

theorem cert_ledger_ge_desc (rad : Nat → Int) (hm : ∀ a b : Nat, a ≤ b → rad a ≤ rad b) (dhat : Int)
    (info desc : Nat) :
    cert rad dhat desc ≤ cert rad dhat (min info desc) :=
  cert_antitone rad hm dhat (Nat.min_le_right _ _)

end HoldoutLedger
