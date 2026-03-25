
## About this dataset

This artifical [dataset](README.md#license) covers 14 days for a fleet of four equipment types with five tools each. 

| Entity Group | Description | Entities |
|--------------|-------------|----------|
| CNC          | CNC         | CNC01, CNC02, CNC03, CNC04, CNC05   |
| PMP          | Pump        | PMP06, PMP07, PMP08, PMP09, PMP10   |
| CPR          | Compressor  | CPR11, CPR12, CPR13, CPR14, CNC15   |
| ARM          | Robotic Arm | ARM16, ARM17, ARM18, ARM19, ARM20   |

Each entity has six defined sensors:
```
- vibration_rms
- temperature_motor
- current_phase_avg
- pressure_level
- rpm
- ambient_temp
```

**Entity Group and Sensor are key parameters that define each SPC chart.**

The sensor data includes a context column for operating_mode: idle, normal, or peak. Only the normal dataset was included for the SPC dataset.

When a sensor drifts off target, the equipment goes down for maintenance to reset the tool to baseline. Sometimes, the maintenance fails and has to be repeated.

The dataset includes additional columns that are not yet supported by the SPC Agent (but planned for future extensions):
- `hours_since_maintenance`: tracks maintenance lifetime, resets after each maintenance
- `failure_type`: stores root cause attribution for each maintenance event There is also an informational column failure_type.

---
### CNC Sample Data

![Image](assets/CNC01.png)

---

### PMP Sample Data
![Image](assets/PMP06.png)

---

### CPR Sample Data
![Image](assets/CPR11.png)

---

### ARM Sample Data
![Image](assets/ARM16.png)

---

### Failure Types by Entity Group
![Image](assets/failure_types.png)