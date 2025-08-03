import numpy as np
from typing import Optional, Tuple, List


class SpatialPerceptionModule:
    """
    Módulo para análisis de percepción espacial que analiza los efectos de las acciones
    en el ambiente basándose en las diferencias entre matrices de estado.
    """
    
    def __init__(self):
        """Inicializar el módulo de percepción espacial."""
        self.matrix_before_action: Optional[List[List[int]]] = None
        self.pending_action: Optional[int] = None
        self.pending_coordinates: Optional[Tuple[int, int]] = None
        self.action_history: List[Tuple[int, Optional[Tuple[int, int]], str]] = []
        
        # Mapeo de números de acción a nombres
        self.action_names = {
            1: "arriba",
            2: "abajo", 
            3: "izquierda",
            4: "derecha",
            5: "barra",
            6: "click"
        }
        
    def prepare_action_analysis(
        self, 
        matrix_before: List[List[int]], 
        action: int, 
        coordinates: Optional[Tuple[int, int]] = None
    ) -> None:
        """
        Preparar el análisis guardando el estado antes de la acción.
        
        Args:
            matrix_before: Matriz del estado antes de ejecutar la acción
            action: Número de acción (1-6)
            coordinates: Coordenadas (x, y) para acción 6, None para otras acciones
        """
        self.matrix_before_action = [row[:] for row in matrix_before]  # Copia profunda
        self.pending_action = action
        self.pending_coordinates = coordinates
        
    def analyze_action_effect(self, matrix_after: List[List[int]]) -> str:
        """
        Analizar el efecto de la acción pendiente después de recibir el nuevo estado.
        
        Args:
            matrix_after: Matriz del estado después de la acción
            
        Returns:
            String con el análisis del efecto de la acción
        """
        if self.matrix_before_action is None or self.pending_action is None:
            return "Error: No hay acción pendiente para analizar."
        
        # Calcular diferencia entre matrices
        difference_matrix = self._calculate_matrix_difference(
            self.matrix_before_action, 
            matrix_after
        )
        
        # Analizar si hubo cambios
        has_changes = np.any(difference_matrix != 0)
        
        # Obtener nombre de la acción
        action_name = self.action_names.get(self.pending_action, f"acción {self.pending_action}")
        
        # Crear mensaje de análisis
        if not has_changes:
            analysis = f"Esa acción ({action_name}) no generó ningún efecto en el ambiente."
        else:
            analysis = "No se puede determinar nada todavía."
        
        # Almacenar en historial
        self.action_history.append((self.pending_action, self.pending_coordinates, analysis))
        
        # Limpiar datos pendientes
        self.matrix_before_action = None
        self.pending_action = None
        self.pending_coordinates = None
        
        return analysis
    
    def get_action_name(self, action_number: int) -> str:
        """
        Obtener el nombre de una acción por su número.
        
        Args:
            action_number: Número de acción (1-6)
            
        Returns:
            Nombre de la acción en español
        """
        return self.action_names.get(action_number, f"acción {action_number}")
        
    def _calculate_matrix_difference(
        self, 
        matrix_before: List[List[int]], 
        matrix_after: List[List[int]]
    ) -> np.ndarray:
        """
        Calcular la diferencia entre dos matrices.
        
        Args:
            matrix_before: Matriz del estado anterior
            matrix_after: Matriz del estado posterior
            
        Returns:
            np.ndarray con la diferencia (after - before)
        """
        try:
            # Convertir a numpy arrays
            before = np.array(matrix_before, dtype=np.int32)
            after = np.array(matrix_after, dtype=np.int32)
            
            # Asegurar que sean matrices 2D
            if before.ndim == 3:
                before = before.squeeze()
            if after.ndim == 3:
                after = after.squeeze()
            
            # Calcular diferencia
            difference = after - before
            
            return difference
            
        except Exception as e:
            print(f"❌ Error al calcular diferencia de matrices: {e}")
            return np.zeros((64, 64), dtype=np.int32)
    
    def get_action_history(self) -> List[Tuple[int, Optional[Tuple[int, int]], str]]:
        """
        Obtener el historial completo de acciones analizadas.
        
        Returns:
            Lista de tuplas (acción, coordenadas, análisis)
        """
        return self.action_history.copy()
    
    def get_last_analysis(self) -> Optional[str]:
        """
        Obtener el último análisis realizado.
        
        Returns:
            String con el último análisis o None si no hay historial
        """
        if not self.action_history:
            return None
        return self.action_history[-1][2]