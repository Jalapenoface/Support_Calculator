from scoring import Inputs, calculate

def test_defaults():
    r=calculate(Inputs())
    assert r['total_cost']==1575
    assert round(r['cost_per_student'],3)==13.125
    assert round(r['effort_minutes_per_student'],1)==22.5
    assert round(r['cost_per_satisfied_student'],2)==15.44
    assert round(r['pedagogical_roi'],2)==31.48
    assert round(r['scalability_index'],1)==4.4
    assert r['efficiency_index']==20
    assert r['resource_utilization']==50
    assert round(r['vitality_score'],1)==56.5
    assert r['vitality_grade']=='B'
