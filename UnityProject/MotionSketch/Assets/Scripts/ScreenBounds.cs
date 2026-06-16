using UnityEngine;

/// <summary>
/// Provides random positions within screen bounds
/// Attach to an empty GameObject in the scene
/// </summary>
public class ScreenBounds : MonoBehaviour
{
    [Header("Screen Bounds (adjust to match your camera)")]
    [SerializeField] private float minX = -8f;
    [SerializeField] private float maxX = 8f;
    [SerializeField] private float minY = -4.5f;
    [SerializeField] private float maxY = 4.5f;
    [SerializeField] private float zPosition = 0f;

    public Vector3 GetRandomPosition()
    {
        return new Vector3(
            Random.Range(minX, maxX),
            Random.Range(minY, maxY),
            zPosition
        );
    }

    /// <summary>
    /// Call this if unsure of bounds - auto calculates from camera
    /// </summary>
    public void CalculateFromCamera()
    {
        Camera cam = Camera.main;
        if (cam == null) return;

        if (cam.orthographic)
        {
            float height = cam.orthographicSize;
            float width = height * cam.aspect;
            minX = -width;
            maxX = width;
            minY = -height;
            maxY = height;
        }

        Debug.Log($"[ScreenBounds] X({minX} to {maxX}), Y({minY} to {maxY})");
    }
}
