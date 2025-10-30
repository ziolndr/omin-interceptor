#!/usr/bin/env python3
"""
ARBITER DOCTRINE SERVICE - MULTI-LAYER DEFENSE
Updated to support Ukrainian multi-tier defense doctrine including:
- Interceptor drones (economical)
- Mobile firing groups (economical)
- Helicopter systems (economical)
- Traditional missile systems (moderate/premium)

Created by: Yaroslav Sherstiuk & Joel Trout
For: Brave1 / Ukrainian Armed Forces deployment
Version: 2.1 - Cost calculations fixed
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import math

# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class CommandLevel(Enum):
    BATTERY = "battery"
    BRIGADE = "brigade"
    THEATER = "theater"

class ThreatType(Enum):
    SHAHED_136 = "Shahed-136"
    SHAHED_131 = "Shahed-131"
    GERAN_2 = "Geran-2"
    LANCET = "Lancet"
    FPV = "FPV дрон"
    ORLAN = "Orlan-10"
    UNKNOWN = "Невідомо"

class SystemType(Enum):
    # Tier 3: Premium systems
    PATRIOT = "Patriot"
    IRIS_T = "IRIS-T"
    
    # Tier 2: Moderate systems
    BUK_M1 = "Buk-M1"
    STINGER = "Stinger"
    IGLA = "Igla"
    
    # Tier 1: Economical systems (NEW)
    INTERCEPTOR_DRONE = "Vampire Interceptor Drone"
    MOBILE_GROUP = "Mobile Firing Group (ЗУ-23-2)"
    HELICOPTER = "Mi-8 Helicopter System"
    
    # Electronic warfare
    ZU_23 = "ЗУ-23-2"
    BUKOVEL = "РЕБ Буковель"

class TargetPriority(Enum):
    CRITICAL = "Критичний"  # Priority 1: Ammo, power, command
    HIGH = "Високий"         # Priority 2: Industrial, transport
    MEDIUM = "Середній"      # Priority 3: Residential, non-critical
    LOW = "Низький"          # Priority 4: Psychological, rural

@dataclass
class ThreatInput:
    """User input: threat parameters"""
    threat_type: ThreatType
    count: int
    range_km: float
    bearing: int
    altitude_m: int
    speed_kmh: float
    target_description: str
    target_priority: TargetPriority
    time_to_impact_minutes: Optional[float] = None

    def __post_init__(self):
        if self.time_to_impact_minutes is None:
            self.time_to_impact_minutes = (self.range_km / self.speed_kmh) * 60

@dataclass
class AvailableSystem:
    """Available air defense system"""
    system_type: SystemType
    count: int
    missiles_available: int  # or units available for non-missile systems
    cost_per_shot: int
    effective_range_km: float
    success_rate: float
    reload_time_minutes: int
    status: str = "READY"
    
    # Additional parameters for economical systems
    setup_time_minutes: int = 0
    weather_dependent: bool = False
    requires_visual: bool = False

@dataclass
class OperationalConstraints:
    """Operational constraints and considerations"""
    limited_ammunition: bool = True
    friendly_forces_nearby: bool = False
    civilian_areas_nearby: bool = False
    weather_conditions: str = "Nominal"
    expected_follow_on_waves: int = 0
    resupply_time_hours: int = 24

@dataclass
class GeneratedOption:
    """Single generated tactical/strategic option"""
    option_id: str
    title: str
    description: str
    template_id: str
    parameters: Dict
    estimated_cost: int
    estimated_success_rate: float
    systems_used: List[str] = field(default_factory=list)

# ============================================================================
# SYSTEM SPECIFICATIONS - REALISTIC COMBAT DATA
# ============================================================================

SYSTEM_SPECS = {
    # Tier 3: Premium
    SystemType.PATRIOT: {
        'cost': 3_000_000,
        'range_km': 160,
        'pk_base': 0.95,
        'optimal_range_km': 80
    },
    SystemType.IRIS_T: {
        'cost': 500_000,
        'range_km': 40,
        'pk_base': 0.93,
        'optimal_range_km': 25
    },
    
    # Tier 2: Moderate
    SystemType.BUK_M1: {
        'cost': 100_000,
        'range_km': 35,
        'pk_base': 0.85,
        'optimal_range_km': 20
    },
    SystemType.STINGER: {
        'cost': 38_000,
        'range_km': 4.8,
        'pk_base': 0.70,
        'optimal_range_km': 3
    },
    SystemType.IGLA: {
        'cost': 25_000,
        'range_km': 5,
        'pk_base': 0.65,
        'optimal_range_km': 3.5
    },
    
    # Tier 1: Economical (FROM COMBAT DATA)
    SystemType.INTERCEPTOR_DRONE: {
        'cost': 5_000,
        'range_km': 20,
        'pk_base': 0.60,
        'optimal_range_km': 15,
        'launch_time_min': 3
    },
    SystemType.MOBILE_GROUP: {
        'cost': 500,
        'range_km': 2.5,
        'pk_base': 0.35,
        'optimal_range_km': 2,
        'setup_time_min': 15,
        'requires_acoustic': True
    },
    SystemType.HELICOPTER: {
        'cost': 2_000,
        'range_km': 10,
        'pk_base': 0.50,
        'optimal_range_km': 8,
        'loiter_time_min': 90,
        'weather_dependent': True,
        'requires_visual': True
    }
}

# ============================================================================
# MULTI-LAYER DOCTRINE TEMPLATES
# ============================================================================

class BatteryDoctrine:
    """
    Battery commander tactical doctrine templates.
    Updated with multi-layer economical defense per Ukrainian doctrine.
    """

    TEMPLATES = {
        'priority_1_immediate': {
            'title': 'ПРІОРИТЕТ 1: Негайний захист критичної інфраструктури',
            'trigger': lambda t, s, c: t.target_priority == TargetPriority.CRITICAL,
            'template': """
ОПЦІЯ: Негайний захист критичної інфраструктури (ПРІОРИТЕТ 1)

ДОКТРИНА: Критична ціль → використати IRIS-T/Patriot НЕГАЙНО

Використати {premium_system} зараз:
• {missiles_allocated}x {premium_system} по {threat_count}x {threat_type}
• Відстань: {current_range}km
• Час до пуску: {time_to_launch} хвилин
• Резерв: {reserve_description}

ОБГРУНТУВАННЯ:
• Ціль "{target_description}" - КРИТИЧНА (боєприпаси, енергія, командування)
• Доктрина вимагає негайного використання преміум систем
• Неприйнятний ризик прориву

ПЕРЕВАГИ:
• {success_rate}% ймовірність знищення
• Максимальна впевненість у захисті
• Відповідає доктрині ПРІОРИТЕТ 1

ВАРТІСТЬ: ${cost:,}
ЙМОВІРНІСТЬ УСПІХУ: {success_rate}%
РІВЕНЬ ПРІОРИТЕТУ: КРИТИЧНИЙ
"""
        },

        'priority_2_drone_first': {
            'title': 'ПРІОРИТЕТ 2: Спочатку дрони, потім ракети',
            'trigger': lambda t, s, c: (
                t.target_priority == TargetPriority.HIGH and 
                t.range_km > 15 and 
                'INTERCEPTOR_DRONE' in [sys.system_type.value for sys in s['systems']]
            ),
            'template': """
ОПЦІЯ: Дрони-перехоплювачі з резервом ракет (ПРІОРИТЕТ 2)

ДОКТРИНА: Високий пріоритет + >15km → спробувати дрони спочатку

ЕТАП 1 (Дрони-перехоплювачі):
• {drone_count}x Vampire дрони на {threat_count}x {threat_type}
• Запуск: {drone_launch_time} хвилин
• Вартість: ${drone_cost:,}
• Ймовірність: {drone_success_rate}%

ЕТАП 2 (Якщо прорив):
• {missile_count}x {missile_system} резерв
• Готовність: {missile_range}km
• Вартість додаткова: ${missile_cost:,}

СЦЕНАРІЇ:
• Дрони успішні: економія ${missile_cost:,} (тільки ${drone_cost:,})
• Дрони не спрацювали: використати {missile_system} (${total_cost:,} загалом)

ПЕРЕВАГИ:
• Економія дорогих ракет якщо дрони спрацюють
• Два шари захисту
• Відповідає доктрині ПРІОРИТЕТ 2

ВАРТІСТЬ: ${cost:,}
ЙМОВІРНІСТЬ УСПІХУ: {combined_success_rate}% (кумулятивна)
"""
        },

        'priority_3_multi_layer': {
            'title': 'ПРІОРИТЕТ 3: Багаторівнева економічна оборона',
            'trigger': lambda t, s, c: (
                t.target_priority in [TargetPriority.MEDIUM, TargetPriority.HIGH] and
                len([sys for sys in s['systems'] if sys.cost_per_shot < 50_000]) >= 2
            ),
            'template': """
ОПЦІЯ: Багаторівнева оборона з економічними системами (ПРІОРИТЕТ 3)

ДОКТРИНА: Середній пріоритет → використати дешеві системи, зберегти ракети

РІВЕНЬ 1 ({range_1}km): {layer_1_system}
• {layer_1_count}x {layer_1_system}
• Вартість: ${layer_1_cost:,}
• Ймовірність: {layer_1_success}%

РІВЕНЬ 2 ({range_2}km): {layer_2_system}
• {layer_2_count}x {layer_2_system} (якщо прорив)
• Вартість: ${layer_2_cost:,}
• Ймовірність: {layer_2_success}%

РІВЕНЬ 3 ({range_3}km): {layer_3_system}
• {layer_3_count}x {layer_3_system} (останній резерв)
• Вартість: ${layer_3_cost:,}
• Ймовірність: {layer_3_success}%

ЕКОНОМІКА:
• Мінімальна вартість: ${min_cost:,} (тільки Рівень 1)
• Типова вартість: ${cost:,} (Рівні 1-2)
• Максимальна вартість: ${max_cost:,} (всі рівні)
• Збережені ракети для наступних хвиль

ПЕРЕВАГИ:
• Множинні шанси перехоплення
• Мінімальна вартість при успіху першого рівня
• {cumulative_success}% кумулятивна ймовірність

ВАРТІСТЬ: ${cost:,}
ЙМОВІРНІСТЬ: {cumulative_success}%
"""
        },

        'priority_4_minimal': {
            'title': 'ПРІОРИТЕТ 4: Мінімальна оборона (прийнятний ризик)',
            'trigger': lambda t, s, c: t.target_priority == TargetPriority.LOW,
            'template': """
ОПЦІЯ: Мінімальна оборона - прийняти обчислений ризик (ПРІОРИТЕТ 4)

ДОКТРИНА: Низький пріоритет → мобільні групи, НЕ витрачати ракети

Використати ТІЛЬКИ економічні системи:
• {mobile_count}x Мобільні групи (ЗУ-23-2)
• {drone_count}x Vampire дрони (якщо доступні)
• {helicopter_count}x Mi-8 гелікоптери (якщо погода дозволяє)

ЗБЕРЕГТИ ВСІ РАКЕТИ для більш критичних цілей

ОБГРУНТУВАННЯ:
• Ціль "{target_description}" - психологічна/сільська місцевість
• Доктрина дозволяє деякі прориви на низькопріоритетних цілях
• Очікується {follow_on_waves} додаткових хвиль - зберегти спроможність

ПРИЙНЯТИЙ РИЗИК:
• {acceptable_losses} з {threat_count} загроз можуть прорватися
• Мінімальна шкода на низькопріоритетній цілі
• Збережено 100% ракет для критичних загроз

ВАРТІСТЬ: ${cost:,} (МІНІМАЛЬНА)
ЙМОВІРНІСТЬ: {success_rate}%
ЗБЕРЕЖЕНІ РАКЕТИ: 100%
"""
        },

        'ew_plus_kinetic_fpv': {
            'title': 'РЕБ + кінетичне ураження (для FPV/Lancet)',
            'trigger': lambda t, s, c: (
                'BUKOVEL' in [sys.system_type.value for sys in s['systems']] and 
                t.threat_type in [ThreatType.FPV, ThreatType.LANCET]
            ),
            'template': """
ОПЦІЯ: Електронна протидія + кінетичне ураження

Комбінований підхід для {threat_type}:

ЕТАП 1: РЕБ "Буковель"
• Спроба збити навігацію дронів
• НУЛЬОВА вартість (багаторазове використання)
• {ew_success_rate}% ймовірність

ЕТАП 2: Кінетичні системи (якщо РЕБ не спрацював)
• {kinetic_count}x {kinetic_system}
• Вартість: ${kinetic_cost:,}
• {kinetic_success_rate}% ймовірність

ЕТАП 3: Резерв
• {backup_system} готовий

ОСОБЛИВІСТЬ {threat_type}:
• Високо вразливі до електронної протидії
• РЕБ ефективний проти GPS/GLONASS навігації
• Економія ракет через використання РЕБ

ПЕРЕВАГИ:
• РЕБ безкоштовний (багаторазово)
• Двошаровий захист
• {combined_success}% комбінована ймовірність

ВАРТІСТЬ: ${cost:,}
ЙМОВІРНІСТЬ: {combined_success}%
"""
        },

        'coordination_with_brigade': {
            'title': 'Координація з бригадою для оптимізації',
            'trigger': lambda t, s, c: s['total_missiles'] < t.count * 2 or c.expected_follow_on_waves > 1,
            'template': """
ОПЦІЯ: Запросити координацію з бригадою

Координація для оптимального розподілу на всю ніч:

МІЙ ВКЛАД:
• Мінімальне використання: {my_allocation}
• Зберігаю {reserve_percent}% резерву

ЗАПИТ ПІДТРИМКИ:
• Джерела: {support_sources}
• Час відповіді: {response_time} хвилин
• Очікувана підтримка: {expected_support}

ОБГРУНТУВАННЯ:
• Очікується {follow_on_waves} додаткових хвиль
• Мої ресурси обмежені ({total_missiles} ракет)
• Оптимізація на рівні бригади більш ефективна

ПЕРЕВАГИ:
• Збереження моїх ресурсів для пізніших хвиль
• Уникнення дублювання зусиль
• Краща координація по регіону

РИЗИКИ:
• Час координації: {response_time} хвилин
• Загроза зараз на {threat_range}km
• Підтримка може не встигнути

ВАРТІСТЬ: ${cost:,} (мінімальна)
ЙМОВІРНІСТЬ: {success_rate}% (залежить від координації)
"""
        }
    }

    @staticmethod
    def calculate_success_rate(system_type: SystemType, range_km: float,
                              threat_type: ThreatType, weather: str = "Nominal") -> float:
        """Calculate success probability based on system, range, threat, and conditions"""
        
        specs = SYSTEM_SPECS.get(system_type)
        if not specs:
            return 0.75  # default
        
        pk_base = specs['pk_base']
        optimal_range = specs['optimal_range_km']
        
        # Range factor
        if range_km > optimal_range:
            range_factor = max(0.6, 1.0 - (range_km - optimal_range) / (optimal_range * 2))
        else:
            range_factor = min(1.0, 0.85 + (optimal_range - range_km) / optimal_range * 0.15)
        
        # Weather degradation for weather-dependent systems
        weather_factor = 1.0
        if system_type == SystemType.HELICOPTER and weather in ["Heavy clouds", "Rain", "Fog"]:
            weather_factor = 0.3  # Can barely operate
        
        return pk_base * range_factor * weather_factor

    @staticmethod
    def generate_options(threat: ThreatInput,
                        systems: List[AvailableSystem],
                        constraints: OperationalConstraints) -> List[GeneratedOption]:
        """Generate 4-8 tactical options based on multi-layer doctrine"""

        # Prepare system summary
        system_summary = {
            'premium_missiles': sum(s.missiles_available for s in systems
                                   if s.cost_per_shot >= 400_000),
            'moderate_missiles': sum(s.missiles_available for s in systems
                                    if 30_000 <= s.cost_per_shot < 400_000),
            'economical_units': sum(s.missiles_available for s in systems
                                   if s.cost_per_shot < 30_000),
            'total_missiles': sum(s.missiles_available for s in systems),
            'system_types': list(set(s.system_type for s in systems)),
            'systems': systems
        }

        options = []

        # Evaluate each template
        for template_id, template_def in BatteryDoctrine.TEMPLATES.items():
            # Check if template triggers
            if not template_def['trigger'](threat, system_summary, constraints):
                continue

            # Calculate parameters for this template
            params = BatteryDoctrine._calculate_parameters(
                template_id, threat, systems, constraints, system_summary
            )

            if params is None:
                continue

            # Fill template
            option_text = template_def['template'].format(**params)

            options.append(GeneratedOption(
                option_id=f"BATTERY_{template_id}_{int(time.time())}",
                title=template_def['title'],
                description=option_text.strip(),
                template_id=template_id,
                parameters=params,
                estimated_cost=params.get('cost', 0),
                estimated_success_rate=params.get('success_rate', 75.0),
                systems_used=params.get('systems_used', [])
            ))

        return options

    @staticmethod
    def _calculate_parameters(template_id: str,
                             threat: ThreatInput,
                             systems: List[AvailableSystem],
                             constraints: OperationalConstraints,
                             system_summary: Dict) -> Optional[Dict]:
        """Calculate specific parameters for template"""

        # Categorize systems
        premium = sorted([s for s in systems if s.cost_per_shot >= 400_000],
                        key=lambda x: x.cost_per_shot, reverse=True)
        moderate = sorted([s for s in systems if 30_000 <= s.cost_per_shot < 400_000],
                         key=lambda x: x.cost_per_shot, reverse=True)
        economical = sorted([s for s in systems if s.cost_per_shot < 30_000],
                           key=lambda x: x.cost_per_shot)

        # Get specific system types
        drones = [s for s in economical if s.system_type == SystemType.INTERCEPTOR_DRONE]
        mobile_groups = [s for s in economical if s.system_type == SystemType.MOBILE_GROUP]
        helicopters = [s for s in economical if s.system_type == SystemType.HELICOPTER]

        if template_id == 'priority_1_immediate':
            if not premium:
                return None
                
            primary = premium[0]
            missiles_needed = min(threat.count, primary.missiles_available)
            success_rate = BatteryDoctrine.calculate_success_rate(
                primary.system_type, threat.range_km, threat.threat_type
            )

            return {
                'premium_system': primary.system_type.value,
                'missiles_allocated': missiles_needed,
                'threat_count': threat.count,
                'threat_type': threat.threat_type.value,
                'current_range': threat.range_km,
                'time_to_launch': 2,
                'target_description': threat.target_description,
                'reserve_description': f"{primary.missiles_available - missiles_needed}x {primary.system_type.value}, всі інші системи",
                'cost': primary.cost_per_shot * missiles_needed,
                'success_rate': int(success_rate * 100),
                'systems_used': [primary.system_type.value]
            }

        elif template_id == 'priority_2_drone_first':
            if not drones or not moderate:
                return None
                
            drone_sys = drones[0]
            missile_sys = moderate[0] if moderate else premium[0] if premium else None
            
            if not missile_sys:
                return None

            drone_count = min(max(2, threat.count), drone_sys.missiles_available)
            missile_count = min(max(2, threat.count // 2), missile_sys.missiles_available)

            drone_success = BatteryDoctrine.calculate_success_rate(
                drone_sys.system_type, threat.range_km * 0.7, threat.threat_type
            )
            missile_success = BatteryDoctrine.calculate_success_rate(
                missile_sys.system_type, threat.range_km * 0.4, threat.threat_type
            )

            # Probability: drones succeed OR (drones fail AND missiles succeed)
            combined = drone_success + (1 - drone_success) * missile_success

            drone_cost = drone_sys.cost_per_shot * drone_count
            missile_cost = missile_sys.cost_per_shot * missile_count

            return {
                'drone_count': drone_count,
                'drone_launch_time': 3,
                'drone_cost': drone_cost,
                'drone_success_rate': int(drone_success * 100),
                'missile_count': missile_count,
                'missile_system': missile_sys.system_type.value,
                'missile_range': int(threat.range_km * 0.4),
                'missile_cost': missile_cost,
                'total_cost': drone_cost + missile_cost,
                'combined_success_rate': int(combined * 100),
                'threat_count': threat.count,
                'threat_type': threat.threat_type.value,
                'cost': drone_cost + missile_cost,  # FIXED: Show total expected cost
                'success_rate': int(combined * 100),
                'systems_used': [drone_sys.system_type.value, missile_sys.system_type.value]
            }

        elif template_id == 'priority_3_multi_layer':
            layers = []
            
            # Build layers from economical to premium
            if economical:
                layers.append(economical[0])
            if moderate:
                layers.append(moderate[0])
            if premium:
                layers.append(premium[0])

            if len(layers) < 2:
                return None

            # Pad if needed
            while len(layers) < 3:
                layers.append(layers[-1])

            layer1, layer2, layer3 = layers[0], layers[1], layers[2]

            # Calculate for each layer
            range1 = threat.range_km * 0.5
            range2 = threat.range_km * 0.35
            range3 = threat.range_km * 0.2

            count1 = min(max(2, threat.count), layer1.missiles_available)
            count2 = min(max(1, threat.count // 2), layer2.missiles_available)
            count3 = min(max(1, threat.count // 3), layer3.missiles_available)

            success1 = BatteryDoctrine.calculate_success_rate(layer1.system_type, range1, threat.threat_type)
            success2 = BatteryDoctrine.calculate_success_rate(layer2.system_type, range2, threat.threat_type)
            success3 = BatteryDoctrine.calculate_success_rate(layer3.system_type, range3, threat.threat_type)

            # Cumulative: 1 - (fail_all_three)
            cumulative = 1 - (1 - success1) * (1 - success2) * (1 - success3)

            cost1 = layer1.cost_per_shot * count1
            cost2 = layer2.cost_per_shot * count2
            cost3 = layer3.cost_per_shot * count3

            return {
                'range_1': int(range1),
                'layer_1_system': layer1.system_type.value,
                'layer_1_count': count1,
                'layer_1_cost': cost1,
                'layer_1_success': int(success1 * 100),
                'range_2': int(range2),
                'layer_2_system': layer2.system_type.value,
                'layer_2_count': count2,
                'layer_2_cost': cost2,
                'layer_2_success': int(success2 * 100),
                'range_3': int(range3),
                'layer_3_system': layer3.system_type.value,
                'layer_3_count': count3,
                'layer_3_cost': cost3,
                'layer_3_success': int(success3 * 100),
                'min_cost': cost1,
                'max_cost': cost1 + cost2 + cost3,
                'cumulative_success': int(cumulative * 100),
                'cost': cost1 + cost2,  # FIXED: Expected cost is first 2 layers
                'success_rate': int(cumulative * 100),
                'systems_used': [layer1.system_type.value, layer2.system_type.value, layer3.system_type.value]
            }

        elif template_id == 'priority_4_minimal':
            mobile_count = len(mobile_groups)
            drone_count = len(drones)
            heli_count = len(helicopters) if constraints.weather_conditions == "Nominal" else 0

            if mobile_count == 0 and drone_count == 0:
                return None

            # Use only economical
            total_cost = 0
            total_success = 0.0

            if mobile_count > 0:
                mobile_sys = mobile_groups[0]
                m_count = min(threat.count, mobile_sys.missiles_available)
                total_cost += mobile_sys.cost_per_shot * m_count
                total_success += BatteryDoctrine.calculate_success_rate(
                    mobile_sys.system_type, 2.0, threat.threat_type
                )

            if drone_count > 0:
                drone_sys = drones[0]
                d_count = min(threat.count, drone_sys.missiles_available)
                total_cost += drone_sys.cost_per_shot * d_count
                success_drone = BatteryDoctrine.calculate_success_rate(
                    drone_sys.system_type, threat.range_km * 0.6, threat.threat_type
                )
                # Combined with mobile
                total_success = 1 - (1 - total_success) * (1 - success_drone)

            acceptable_losses = max(1, int(threat.count * (1 - total_success)))

            return {
                'mobile_count': mobile_count if mobile_count > 0 else 0,
                'drone_count': drone_count if drone_count > 0 else 0,
                'helicopter_count': heli_count,
                'target_description': threat.target_description,
                'follow_on_waves': constraints.expected_follow_on_waves,
                'threat_count': threat.count,
                'acceptable_losses': acceptable_losses,
                'cost': total_cost,
                'success_rate': int(total_success * 100),
                'systems_used': [s.system_type.value for s in (mobile_groups + drones + helicopters)[:3]]
            }

        elif template_id == 'ew_plus_kinetic_fpv':
            kinetic_sys = moderate[0] if moderate else economical[0] if economical else None
            if not kinetic_sys:
                return None

            kinetic_count = max(2, threat.count // 2)

            ew_success = 0.75
            kinetic_success = BatteryDoctrine.calculate_success_rate(
                kinetic_sys.system_type, threat.range_km * 0.5, threat.threat_type
            )
            combined = 1 - (1 - ew_success) * (1 - kinetic_success)

            backup = economical[0] if economical else kinetic_sys

            kinetic_cost = kinetic_sys.cost_per_shot * kinetic_count

            return {
                'threat_type': threat.threat_type.value,
                'ew_success_rate': int(ew_success * 100),
                'kinetic_count': kinetic_count,
                'kinetic_system': kinetic_sys.system_type.value,
                'kinetic_cost': kinetic_cost,
                'kinetic_success_rate': int(kinetic_success * 100),
                'backup_system': backup.system_type.value,
                'combined_success': int(combined * 100),
                'cost': kinetic_cost,  # EW is free, show kinetic cost
                'success_rate': int(combined * 100),
                'systems_used': ['РЕБ Буковель', kinetic_sys.system_type.value]
            }

        elif template_id == 'coordination_with_brigade':
            minimal_sys = economical[0] if economical else moderate[0] if moderate else premium[0]
            if not minimal_sys:
                return None

            return {
                'my_allocation': f"1x {minimal_sys.system_type.value}",
                'reserve_percent': 90,
                'support_sources': "Сусідні батареї, бригадний резерв, РЕБ підтримка",
                'response_time': 3,
                'expected_support': "Координоване використання ресурсів по регіону",
                'follow_on_waves': constraints.expected_follow_on_waves,
                'total_missiles': system_summary['total_missiles'],
                'threat_range': threat.range_km,
                'cost': minimal_sys.cost_per_shot,  # Cost of minimal allocation
                'success_rate': 70,
                'systems_used': ['Координація']
            }

        return None

# ============================================================================
# ARBITER INTEGRATION (unchanged)
# ============================================================================

class ARBITERDoctrineService:
    """
    Main service: Generate options + evaluate with ARBITER
    """

    def __init__(self, arbiter_url: str = "https://api.arbiter.traut.ai/v1/compare"):
        self.arbiter_url = arbiter_url

    def process_battery_situation(self,
                                  threat: ThreatInput,
                                  systems: List[AvailableSystem],
                                  constraints: OperationalConstraints,
                                  commander_context: str = "") -> Dict:
        """
        Complete battery-level processing:
        1. Generate tactical options from doctrine
        2. Send to ARBITER for evaluation
        3. Return ranked recommendations
        """

        print(f"\n{'='*80}")
        print(f"BATTERY DOCTRINE SERVICE - Multi-Layer Defense")
        print(f"{'='*80}\n")

        # Step 1: Generate options
        print(f"⚙️  Generating tactical options from multi-layer doctrine...")
        start = time.time()

        options = BatteryDoctrine.generate_options(threat, systems, constraints)

        gen_time = time.time() - start
        print(f"✓ Generated {len(options)} options in {gen_time*1000:.0f}ms\n")

        for i, opt in enumerate(options, 1):
            print(f"{i}. {opt.title}")
            print(f"   Template: {opt.template_id}")
            print(f"   Cost: ${opt.estimated_cost:,}, Success: {opt.estimated_success_rate:.0f}%")
            print(f"   Systems: {', '.join(opt.systems_used)}\n")

        # Step 2: Build query for ARBITER
        query = self._build_battery_query(threat, systems, constraints, commander_context)
        candidates = [opt.description for opt in options]

        # Step 3: Query ARBITER
        print(f"⚡ Querying ARBITER for coherence evaluation...")
        arbiter_result = self._query_arbiter(query, candidates)

        if not arbiter_result['success']:
            return {
                'success': False,
                'error': arbiter_result.get('error', 'Unknown'),
                'generated_options': options
            }

        # Step 4: Combine results
        ranked_options = self._combine_results(options, arbiter_result['result'])

        return {
            'success': True,
            'generation_time_ms': gen_time * 1000,
            'arbiter_latency_ms': arbiter_result['latency'] * 1000,
            'total_time_ms': (gen_time + arbiter_result['latency']) * 1000,
            'options_generated': len(options),
            'ranked_recommendations': ranked_options,
            'query': query,
            'threat_summary': {
                'type': threat.threat_type.value,
                'count': threat.count,
                'range_km': threat.range_km,
                'priority': threat.target_priority.value,
                'time_to_impact_min': threat.time_to_impact_minutes
            }
        }

    def _build_battery_query(self, threat: ThreatInput,
                            systems: List[AvailableSystem],
                            constraints: OperationalConstraints,
                            context: str) -> str:
        """Build semantic query for battery commander"""

        query = f"""
Я командир батареї ППО біля {threat.target_description}.
Мій досвід: {context if context else "2 роки оборони від російських атак"}

ПОТОЧНА ЗАГРОЗА:
• Тип: {threat.count}x {threat.threat_type.value}
• Дальність: {threat.range_km}км та наближаються
• Швидкість: {threat.speed_kmh}км/год
• Висота: {threat.altitude_m}м
• Курс: {threat.bearing}° → {threat.target_description}
• Час до удару: {threat.time_to_impact_minutes:.1f} хвилин
• ПРІОРИТЕТ ЦІЛІ: {threat.target_priority.value}

МОЇ ДОСТУПНІ СИСТЕМИ:
"""

        for sys in systems:
            query += f"""
• {sys.system_type.value}: {sys.missiles_available} {'ракет' if 'IRIS' in sys.system_type.value or 'Patriot' in sys.system_type.value else 'одиниць'} доступно
  - Вартість: ${sys.cost_per_shot:,} за постріл
  - Дальність: {sys.effective_range_km}km
  - Ефективність: {int(sys.success_rate * 100)}%
  - Статус: {sys.status}
"""

        query += "\nОБМЕЖЕННЯ:\n"
        if constraints.limited_ammunition:
            query += f"• ОБМЕЖЕНІ БОЄПРИПАСИ - поповнення через {constraints.resupply_time_hours} годин\n"
        if constraints.expected_follow_on_waves > 0:
            query += f"• Очікується {constraints.expected_follow_on_waves} додаткових хвиль атак сьогодні\n"
        if constraints.civilian_areas_nearby:
            query += "• Цивільні об'єкти поблизу\n"

        query += f"\nПогода: {constraints.weather_conditions}\n"
        query += "\nПотрібна ТАКТИЧНА РЕКОМЕНДАЦІЯ згідно з багаторівневою доктриною оборони.\n"

        return query.strip()

    def _query_arbiter(self, query: str, candidates: List[str]) -> Dict:
        """Query ARBITER API"""

        try:
            start = time.time()

            response = requests.post(
                self.arbiter_url,
                json={
                    "query": query,
                    "candidates": candidates,
                    "use_freq": True,
                    "top_k": len(candidates)
                },
                timeout=30
            )

            latency = time.time() - start

            if response.status_code == 200:
                return {
                    'success': True,
                    'result': response.json(),
                    'latency': latency
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}",
                    'latency': latency
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'latency': 0
            }

    def _combine_results(self, options: List[GeneratedOption],
                        arbiter_result: Dict) -> List[Dict]:
        """Combine generated options with ARBITER rankings"""

        ranked = []

        for i, arb_option in enumerate(arbiter_result['top'], 1):
            # Find matching generated option
            matching = None
            for opt in options:
                if opt.description == arb_option['text']:
                    matching = opt
                    break

            ranked.append({
                'rank': i,
                'coherence': arb_option['score'],
                'title': matching.title if matching else f"Option {i}",
                'description': arb_option['text'],
                'template_id': matching.template_id if matching else 'unknown',
                'estimated_cost': matching.estimated_cost if matching else 0,
                'estimated_success_rate': matching.estimated_success_rate if matching else 0,
                'systems_used': matching.systems_used if matching else [],
                'recommendation_level': 'HIGH' if arb_option['score'] > 0.80 else 'MEDIUM' if arb_option['score'] > 0.70 else 'LOW'
            })

        return ranked

# ============================================================================
# VALIDATION SCENARIO - ODESA OCTOBER 19, 2024
# ============================================================================

def validate_odesa_october_19():
    """
    Validation scenario: Odesa October 19, 2024
    Real combat data vs Omin recommendations
    """

    print("""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                     OMIN VALIDATION - ODESA OCTOBER 19, 2024                         ║
║                                                                                       ║
║  Scenario: 12x Shahed-136 multi-priority targets                                    ║
║  Actual cost: €2.6M, Result: 9/12 killed                                            ║
║  Testing: What would Omin recommend?                                                 ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
    """)

    # Define threat (simplified to port + power priority)
    threat = ThreatInput(
        threat_type=ThreatType.SHAHED_136,
        count=5,  # 2 port + 3 power (critical)
        range_km=25.0,
        bearing=45,
        altitude_m=1200,
        speed_kmh=185,
        target_description="Порт та електростанція (КРИТИЧНІ)",
        target_priority=TargetPriority.CRITICAL
    )

    # Define available systems (what they had)
    systems = [
        AvailableSystem(
            system_type=SystemType.IRIS_T,
            count=2,
            missiles_available=6,
            cost_per_shot=500_000,
            effective_range_km=40,
            success_rate=0.93,
            reload_time_minutes=720
        ),
        AvailableSystem(
            system_type=SystemType.BUK_M1,
            count=1,
            missiles_available=3,
            cost_per_shot=100_000,
            effective_range_km=35,
            success_rate=0.85,
            reload_time_minutes=480
        ),
        AvailableSystem(
            system_type=SystemType.STINGER,
            count=4,
            missiles_available=8,
            cost_per_shot=40_000,
            effective_range_km=5,
            success_rate=0.70,
            reload_time_minutes=120
        ),
        AvailableSystem(
            system_type=SystemType.INTERCEPTOR_DRONE,
            count=4,
            missiles_available=4,
            cost_per_shot=5_000,
            effective_range_km=20,
            success_rate=0.60,
            reload_time_minutes=30
        ),
        AvailableSystem(
            system_type=SystemType.MOBILE_GROUP,
            count=2,
            missiles_available=2,
            cost_per_shot=500,
            effective_range_km=2.5,
            success_rate=0.35,
            reload_time_minutes=15,
            setup_time_minutes=15
        ),
        AvailableSystem(
            system_type=SystemType.HELICOPTER,
            count=1,
            missiles_available=1,
            cost_per_shot=2_000,
            effective_range_km=10,
            success_rate=0.50,
            reload_time_minutes=90,
            weather_dependent=True
        )
    ]

    # Define constraints
    constraints = OperationalConstraints(
        limited_ammunition=True,
        weather_conditions="Marginal",
        expected_follow_on_waves=2,
        resupply_time_hours=24
    )

    # Process
    service = ARBITERDoctrineService()

    result = service.process_battery_situation(
        threat=threat,
        systems=systems,
        constraints=constraints,
        commander_context="Odesa sector, October 19, 2024 validation"
    )

    # Display results
    if result['success']:
        print(f"\n{'='*80}")
        print(f"OMIN RECOMMENDATIONS VS ACTUAL")
        print(f"{'='*80}\n")

        print(f"⏱️  Performance:")
        print(f"   Total time: {result['total_time_ms']:.0f}ms\n")

        print(f"📊 Top Recommendation:\n")

        top_rec = result['ranked_recommendations'][0]
        print(f"🟢 #{top_rec['rank']} | Coherence: {top_rec['coherence']:.4f}")
        print(f"   {top_rec['title']}")
        print(f"   Cost: ${top_rec['estimated_cost']:,}")
        print(f"   Success: {top_rec['estimated_success_rate']}%")
        print(f"   Systems: {', '.join(top_rec['systems_used'])}\n")

        print(f"COMPARISON:")
        print(f"   Actual (Oct 19): €2.6M spent, 9/12 killed (75%)")
        print(f"   Omin recommends: ${top_rec['estimated_cost']:,}, {top_rec['estimated_success_rate']}% predicted\n")

        if top_rec['estimated_cost'] < 2_600_000:
            savings = 2_600_000 - top_rec['estimated_cost']
            print(f"✅ Potential savings: ${savings:,}")
        
        print(f"\n✅ Doctrine service validation complete")

    else:
        print(f"\n❌ Error: {result.get('error')}")

if __name__ == "__main__":
    validate_odesa_october_19()
