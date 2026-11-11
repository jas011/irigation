import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
    MapContainer,
    TileLayer,
    Marker,
    Popup,
    useMap,
    Polygon as LeafletPolygon,
    GeoJSON
} from "react-leaflet";
import L from "leaflet";
import "@geoman-io/leaflet-geoman-free";
import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";

import {
    Search,
    Navigation,
    AlertTriangle,
    Info,
    Trash2,
    Globe,
    Map as MapIcon,
    CheckCircle,
    MapPin,
    Loader2
} from "lucide-react";

import ApiService from "../../services/api";
import { useFieldContext } from "../../layouts/DashboardLayout";
import "../Dashboard.css";

const getCropOverlayColor = (crop?: string) => {
    if (crop === "Paddy") return "#10b981";
    if (crop === "Wheat") return "#eab308";
    if (crop === "Cotton") return "#06b6d4";
    if (crop === "Maize") return "#f97316";
    if (crop === "Bare Soil") return "#78350f";
    if (crop === "Water") return "#3b82f6";
    if (crop === "Non-Crop") return "#6b7280";
    return "#a855f7";
};

const getStressOverlayColor = (stress?: string) => {
    if (stress === "No Stress") return "#3b82f6";
    if (stress === "Low Stress") return "#22c55e";
    if (stress === "Moderate Stress") return "#eab308";
    if (stress === "High Stress") return "#f97316";
    if (stress === "Severe Stress") return "#ef4444";
    return "#10b981";
};

// Fix Leaflet marker icon issues in React
// @ts-ignore
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
    iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
    shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

// Component to handle map actions (flyTo, fitBounds)
const MapController: React.FC<{
    center: [number, number] | null;
    bounds: L.LatLngBoundsExpression | null;
}> = ({ center, bounds }) => {
    const map = useMap();

    useEffect(() => {
        if (bounds) {
            map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
        } else if (center) {
            map.flyTo(center, 15, { animate: true });
        }
    }, [center, bounds, map]);

    return null;
};

// Component to inject Geoman Controls and hook events
interface GeomanProps {
    onPolygonCreated: (coords: number[][][]) => void;
    onPolygonEdited: (coords: number[][][]) => void;
    onPolygonRemoved: () => void;
}

const GeomanControls: React.FC<GeomanProps> = ({
    onPolygonCreated,
    onPolygonEdited,
    onPolygonRemoved
}) => {
    const map = useMap();
    const createdLayerRef = useRef<L.Layer | null>(null);

    useEffect(() => {
        if (!map) return;

        // Initialize Geoman Controls
        map.pm.addControls({
            position: "topright",
            drawMarker: false,
            drawCircleMarker: false,
            drawPolyline: false,
            drawRectangle: false,
            drawCircle: false,
            drawText: false,
            cutPolygon: false,
            dragMode: false,
            drawPolygon: true,
            editMode: true,
            removalMode: true,
            rotateMode: false,
            oneBlock: true
        });

        // Custom Green Styling for Drew Polygons
        map.pm.setPathOptions({
            color: "#16803d",
            fillColor: "#22c55e",
            fillOpacity: 0.3,
            weight: 3
        });

        // Hook Create Event
        map.on("pm:create", (e: any) => {
            const layer = e.layer;
            createdLayerRef.current = layer;

            const geojson = layer.toGeoJSON();
            const coords = geojson.geometry.coordinates; // [[[lng, lat], ...]]

            onPolygonCreated(coords);

            // Listen to edits on this layer
            layer.on("pm:edit", (evt: any) => {
                const updatedGeojson = evt.layer.toGeoJSON();
                onPolygonEdited(updatedGeojson.geometry.coordinates);
            });

            // Listen to removal
            layer.on("pm:remove", () => {
                createdLayerRef.current = null;
                onPolygonRemoved();
            });
        });

        return () => {
            map.off("pm:create");
            map.pm.removeControls();
        };
    }, [map, onPolygonCreated, onPolygonEdited, onPolygonRemoved]);

    return null;
};

const AreaSelection: React.FC = () => {
    const navigate = useNavigate();
    const {
        setActiveFieldId,
        selectedFieldData,
        setSelectedFieldData,
        areaUnit,
        mapOverlayMode,
        cropGrid,
        moistureGrid
    } = useFieldContext();

    // Map settings
    const [mapCenter, setMapCenter] = useState<[number, number]>([30.9010, 75.8573]); // Default Ludhiana
    const [mapBounds, setMapBounds] = useState<L.LatLngBoundsExpression | null>(null);
    const [isSatellite, setIsSatellite] = useState<boolean>(true); // True = Satellite Imagery default

    // Search states
    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<any[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [searchError, setSearchError] = useState<string | null>(null);

    const [gpsLocation, setGpsLocation] = useState<[number, number] | null>(null);

    // Validation/API Response State
    const [validationData, setValidationData] = useState<any | null>(null);
    const [isValidating, setIsValidating] = useState(false);
    const [validationError, setValidationError] = useState<string | null>(null);

    // AI Field Verification Middleware State
    const [isVerifyingAI, setIsVerifyingAI] = useState(false);
    const [aiRejectionData, setAiRejectionData] = useState<{
        land_type: string;
        user_friendly_category?: string;
        reason: string;
        confidence: number;
        visual_features_observed?: string[];
        all_possibilities?: Record<string, number>;
    } | null>(null);
    const [aiErrorData, setAiErrorData] = useState<string | null>(null);

    // Confirmation/Registration State
    const [isSaving, setIsSaving] = useState(false);
    const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);
    const [registeredFieldId, setRegisteredFieldId] = useState<string | null>(null);

    const mapRef = useRef<any>(null);

    // If a field was selected from History context, center map and display it
    useEffect(() => {
        if (selectedFieldData) {
            setValidationData({
                valid: true,
                geometry_valid: true,
                area_valid: true,
                area_m2: selectedFieldData.area_m2,
                area_hectares: selectedFieldData.area_hectares,
                area_acres: selectedFieldData.area_acres,
                perimeter_m: selectedFieldData.perimeter_m,
                centroid: {
                    latitude: selectedFieldData.latitude,
                    longitude: selectedFieldData.longitude
                },
                location: {
                    village: selectedFieldData.village,
                    district: selectedFieldData.district,
                    state: selectedFieldData.state,
                    country: selectedFieldData.country,
                    postal_code: selectedFieldData.postal_code
                },
                geometry: selectedFieldData.geometry,
                message: "Field fetched from history database."
            });

            // Center map on centroid
            setMapCenter([selectedFieldData.latitude, selectedFieldData.longitude]);

            // Calculate Bounds to fit
            const outerRing = selectedFieldData.geometry.coordinates[0];
            const latLngs = outerRing.map((pt: number[]) => [pt[1], pt[0]] as [number, number]);
            const bounds = L.latLngBounds(latLngs);
            setMapBounds(bounds);
        }
    }, [selectedFieldData]);

    // Geolocation API handler
    const handleUseMyLocation = () => {
        if (!navigator.geolocation) {
            setValidationError("Geolocation is not supported by your browser.");
            return;
        }

        setValidationError(null);
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const { latitude, longitude } = position.coords;
                const coords: [number, number] = [latitude, longitude];
                setGpsLocation(coords);
                setMapCenter(coords);
                // Clean bounds so it flies to center
                setMapBounds(null);
            },
            (error) => {
                let msg = "Unable to retrieve your location.";
                if (error.code === error.PERMISSION_DENIED) {
                    msg = "Location permission denied by user.";
                }
                setValidationError(msg);
            },
            { enableHighAccuracy: true, timeout: 8000 }
        );
    };

    // Location search using OpenStreetMap Nominatim Search API
    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!searchQuery.trim()) return;

        setIsSearching(true);
        setSearchError(null);
        setSearchResults([]);

        const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(searchQuery)}&format=json&limit=5&addressdetails=1`;
        try {
            const res = await fetch(url, {
                headers: { "User-Agent": "AgriSense-Advisor/1.0" }
            });
            if (res.ok) {
                const data = await res.json();
                if (data.length === 0) {
                    setSearchError("No locations found. Try entering a village, town, or district name.");
                } else {
                    setSearchResults(data);
                }
            } else {
                setSearchError("Search API failed. Please try again.");
            }
        } catch (err) {
            setSearchError("Unable to reach search service. Check internet connection.");
        } finally {
            setIsSearching(false);
        }
    };

    const handleSelectSearchResult = (res: any) => {
        const lat = parseFloat(res.lat);
        const lon = parseFloat(res.lon);
        setMapCenter([lat, lon]);
        setMapBounds(null);
        setSearchResults([]);
        setSearchQuery(res.display_name);
    };

    // Geometry Validation Endpoint triggers
    const triggerGeometryValidation = async (coords: number[][][]) => {
        setIsValidating(true);
        setValidationError(null);
        setSaveSuccessMsg(null);
        setRegisteredFieldId(null);

        const geometry = {
            type: "Polygon",
            coordinates: coords
        };

        try {
            const result = await ApiService.validateField(geometry);
            setValidationData(result);
            if (!result.valid) {
                setValidationError(result.message);
            }
        } catch (err: any) {
            setValidationError(err.message || "Failed to validate field boundary with backend service.");
        } finally {
            setIsValidating(false);
        }
    };

    // Layer Drawing Callback triggers
    const onPolygonCreated = (coords: number[][][]) => {
        triggerGeometryValidation(coords);
    };

    const onPolygonEdited = (coords: number[][][]) => {
        triggerGeometryValidation(coords);
    };

    const onPolygonRemoved = () => {
        setValidationData(null);
        setValidationError(null);
        setSaveSuccessMsg(null);
        setRegisteredFieldId(null);
        setActiveFieldId(null);
        setAiRejectionData(null);
        setAiErrorData(null);
    };

    // Reset drawing layers on map
    const handleRedraw = () => {
        if (mapRef.current) {
            const map = mapRef.current;
            // Clear geoman drawn layers
            map.eachLayer((layer: any) => {
                if (layer.pm && layer !== map) {
                    map.removeLayer(layer);
                }
            });
        }
        onPolygonRemoved();
    };

    // Save the Field (Confirm Field) with AI Field Verification Middleware
    const handleConfirmField = async () => {
        if (!validationData || !validationData.valid || !validationData.geometry) return;

        setIsVerifyingAI(true);
        setAiRejectionData(null);
        setAiErrorData(null);
        setValidationError(null);
        setSaveSuccessMsg(null);

        try {
            // Step 1: AI Field Verification Middleware
            const aiResult = await ApiService.verifyFieldAI(validationData.geometry);

            if (!aiResult.is_field) {
                setAiRejectionData({
                    land_type: aiResult.land_type,
                    user_friendly_category: aiResult.user_friendly_category,
                    reason: aiResult.reason,
                    confidence: aiResult.confidence,
                    visual_features_observed: aiResult.visual_features_observed,
                    all_possibilities: aiResult.all_possibilities
                });
                setIsVerifyingAI(false);
                return;
            }

            // Step 2: Valid agricultural field -> Proceed to save and navigate to Phase 2
            setIsSaving(true);
            const fieldPayload = {
                geometry: validationData.geometry,
                location: validationData.location
            };

            const savedField = await ApiService.createField(fieldPayload.geometry, fieldPayload.location);

            setSaveSuccessMsg("Field successfully registered.");
            setRegisteredFieldId(savedField.field_id);
            setActiveFieldId(savedField.field_id);
            setSelectedFieldData(savedField);
            localStorage.removeItem("agrisense_crop_result");
            localStorage.removeItem("agrisense_moisture_result");
            sessionStorage.setItem("agrisense_stage_direction", "forward");
            navigate("/crop-analysis");
        } catch (err: any) {
            const errorMsg = err.message || "Failed to verify or register field. Please retry.";
            setValidationError(errorMsg);
            setAiErrorData(errorMsg);
        } finally {
            setIsVerifyingAI(false);
            setIsSaving(false);
        }
    };

    const formatArea = (ha: number, ac: number) => {
        if (areaUnit === "acres") {
            return `${ac.toFixed(2)} ac`;
        }
        return `${ha.toFixed(2)} ha`;
    };

    return (
        <div className="dashboard-grid-container">

            {/* Title Banner */}
            <div className="dashboard-section-header select-area-header">
                <h1 className="dashboard-section-title select-area-title">
                    <MapPin color="#66ff00" size={32} />
                    <span>Select Your Field Area</span>
                </h1>
                <p className="dashboard-section-subtitle select-area-subtitle">
                    Search your location, use GPS, or use the drawing tools to define your farm boundary.
                </p>
            </div>

            {/* SUCCESS / ERROR ALERTS */}
            {validationError && (
                <div className="alert-container alert-danger" style={{ marginBottom: 0 }}>
                    <AlertTriangle size={18} style={{ flexShrink: 0 }} />
                    <div>
                        <strong>Validation Alert: </strong>
                        <span>{validationError}</span>
                    </div>
                </div>
            )}

            {saveSuccessMsg && (
                <div className="alert-container alert-success" style={{ marginBottom: 0 }}>
                    <CheckCircle size={18} style={{ flexShrink: 0 }} />
                    <div>
                        <strong>Success: </strong> {saveSuccessMsg}{" "}
                        {registeredFieldId && (
                            <span>
                                Registered Field ID: <strong>{registeredFieldId}</strong>. Ready for satellite analysis.
                            </span>
                        )}
                    </div>
                </div>
            )}

            {/* DASHBOARD INPUT BLOCK: THREE COLUMNS */}
            <div className="dashboard-three-columns">

                {/* COLUMN 1: FIELD SEARCH & LOCATION SELECTION PANEL */}
                <div className="field-search-panel">
                    <div>
                        <h3 className="field-search-title">Select Your Field</h3>
                        <p className="field-search-subtitle">
                            Search location or drop a pin on map
                        </p>
                    </div>

                    {/* Search Box */}
                    <form className="search-form" onSubmit={handleSearch}>
                        <input
                            type="text"
                            placeholder="Search location, village, city..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            disabled={isSearching}
                        />
                        <button
                            type="submit"
                            disabled={isSearching}
                        >
                            <Search size={16} />
                        </button>
                    </form>

                    {/* Search dropdown results */}
                    {searchResults.length > 0 && (
                        <div className="search-results-dropdown">
                            {searchResults.map((res, i) => (
                                <div
                                    key={i}
                                    onClick={() => handleSelectSearchResult(res)}
                                    className="search-result-row"
                                >
                                    {res.display_name}
                                </div>
                            ))}
                        </div>
                    )}

                    {searchError && (
                        <span style={{ fontSize: "11px", color: "var(--color-danger)" }}>{searchError}</span>
                    )}

                    {/* GPS Button */}
                    <button
                        onClick={handleUseMyLocation}
                        className="gps-btn"
                    >
                        <Navigation size={14} />
                        <span>Use My Location (GPS)</span>
                    </button>

                    <hr style={{ border: 0, borderTop: "1px solid var(--border-color)" }} />

                    {/* Selected Address Display */}
                    <div className="location-display">
                        <h4 className="location-label">
                            Selected Location
                        </h4>

                        <div className="location-info-container">
                            <div className="location-info-row">
                                <span className="location-info-label">Village:</span>
                                <span className="location-info-value">
                                    {validationData?.location?.village || selectedFieldData?.village || "—"}
                                </span>
                            </div>
                            <div className="location-info-row">
                                <span className="location-info-label">District:</span>
                                <span className="location-info-value">
                                    {validationData?.location?.district || selectedFieldData?.district || "—"}
                                </span>
                            </div>
                            <div className="location-info-row">
                                <span className="location-info-label">State:</span>
                                <span className="location-info-value">
                                    {validationData?.location?.state || selectedFieldData?.state || "—"}
                                </span>
                            </div>
                            <div className="location-info-row">
                                <span className="location-info-label">Area:</span>
                                <span className="location-area-value">
                                    {validationData?.area_hectares ? formatArea(validationData.area_hectares, validationData.area_acres) : "—"}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Confirm field submission button */}
                    <button
                        onClick={handleConfirmField}
                        disabled={!validationData?.valid || isSaving || isVerifyingAI || !!registeredFieldId}
                        className="confirm-field-btn"
                    >
                        {isVerifyingAI ? "Verifying Field with AI..." : isSaving ? "Registering Field..." : registeredFieldId ? "Field Confirmed ✓" : "Confirm Field"}
                    </button>
                </div>

                {/* COLUMN 2: INTERACTIVE LEAFLET MAP */}
                <div className="map-container">
                    <div className="map-wrapper">
                        <MapContainer
                            center={mapCenter}
                            zoom={14}
                            className="map-leaflet"
                            ref={(ref) => { if (ref) mapRef.current = ref; }}
                        >
                            {/* Tile Switcher (Satellite vs Standard Vector) */}
                            {isSatellite ? (
                                <TileLayer
                                    attribution="Esri, DigitalGlobe, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA, USGS, AeroGRID, IGN, and the GIS User Community"
                                    url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                                />
                            ) : (
                                <TileLayer
                                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                                />
                            )}

                            {/* GPS Point Marker */}
                            {gpsLocation && (
                                <Marker position={gpsLocation}>
                                    <Popup>Your current location</Popup>
                                </Marker>
                            )}

                            {/* Center Controller helper */}
                            <MapController
                                center={mapCenter}
                                bounds={mapBounds}
                            />

                            {/* Geoman Drawing Controls */}
                            <GeomanControls
                                onPolygonCreated={onPolygonCreated}
                                onPolygonEdited={onPolygonEdited}
                                onPolygonRemoved={onPolygonRemoved}
                            />

                            {/* Draw Existing Field Geometry from History */}
                            {selectedFieldData && (
                                <LeafletPolygon
                                    positions={selectedFieldData.geometry.coordinates[0].map((pt: number[]) => [pt[1], pt[0]])}
                                    pathOptions={{ color: "#16803d", fillColor: "#22c55e", fillOpacity: 0.35, weight: 3 }}
                                />
                            )}

                            {/* Crop Overlay Grid */}
                            {mapOverlayMode === "crop" && cropGrid && (
                                <GeoJSON
                                    key={`crop-grid-${cropGrid.features?.length}`}
                                    data={cropGrid}
                                    style={(feature: any) => {
                                        const fillColor = getCropOverlayColor(feature?.properties?.crop);
                                        return {
                                            color: fillColor,
                                            fillColor,
                                            fillOpacity: 0.85,
                                            weight: 1
                                        };
                                    }}
                                    pointToLayer={(feature: any, latlng: L.LatLng) => {
                                        const fillColor = getCropOverlayColor(feature?.properties?.crop);
                                        
                                        return L.circle(latlng, {
                                            radius: 5,
                                            color: fillColor,
                                            fillColor: fillColor,
                                            fillOpacity: 0.85,
                                            weight: 1
                                        });
                                    }}
                                />
                            )}

                            {/* Moisture Overlay Grid */}
                            {mapOverlayMode === "moisture" && moistureGrid && (
                                <GeoJSON
                                    key={`moisture-grid-${moistureGrid.features?.length}`}
                                    data={moistureGrid}
                                    style={(feature: any) => {
                                        const fillColor = getStressOverlayColor(feature?.properties?.stress_class);
                                        return {
                                            color: fillColor,
                                            fillColor,
                                            fillOpacity: 0.85,
                                            weight: 1
                                        };
                                    }}
                                    pointToLayer={(feature: any, latlng: L.LatLng) => {
                                        const fillColor = getStressOverlayColor(feature?.properties?.stress_class);
                                        
                                        return L.circle(latlng, {
                                            radius: 5,
                                            color: fillColor,
                                            fillColor: fillColor,
                                            fillOpacity: 0.85,
                                            weight: 1
                                        });
                                    }}
                                />
                            )}
                        </MapContainer>

                        {/* Map Layer Switcher Button floating top-left */}
                        <div style={{ position: "absolute", top: "12px", left: "50px", zIndex: 10 }}>
                            <button
                                onClick={() => setIsSatellite(!isSatellite)}
                                className="layer-toggle-btn"
                            >
                                {isSatellite ? <Globe size={14} /> : <MapIcon size={14} />}
                                <span>{isSatellite ? "Switch to Map" : "Switch to Satellite"}</span>
                            </button>
                        </div>

                        {/* Bottom Info Status Overlay (Area & Perimeter & Redraw) */}
                        <div className="map-bottom-bar">
                            <div className="map-status-text">
                                {validationData ? (
                                    <span>
                                        Area: <strong className="map-stats-strong">{formatArea(validationData.area_hectares, validationData.area_acres)}</strong>
                                        <span className="map-stat-separator">|</span>
                                        Perimeter: <strong className="map-stats-strong">{(validationData.perimeter_m / 1000).toFixed(2)} km</strong>
                                    </span>
                                ) : (
                                    <span className="map-status-muted">Sketch a polygon on map to calculate metrics</span>
                                )}
                            </div>

                            <div className="map-actions">
                                <button
                                    onClick={handleRedraw}
                                    className="redraw-btn"
                                >
                                    <Trash2 size={12} />
                                    <span>Redraw</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* COLUMN 3: FIELD DETAILS & VALIDATION SUMMARY CARD */}
                <div className="field-details-panel">
                    {/* Header Details */}
                    <div>
                        <h3 className="field-details-title">Field Details</h3>
                        <p className="field-details-subtitle">
                            Geometric boundaries properties
                        </p>
                    </div>

                    {/* Latitude & Longitude Details */}
                    <div className="coordinates-grid">
                        <div className="coordinate-card">
                            <div className="coordinate-label">
                                <MapPin size={12} color="var(--primary-green)" />
                                <span>Latitude</span>
                            </div>
                            <span className="coordinate-value">
                                {validationData?.centroid?.latitude ? `${validationData.centroid.latitude.toFixed(5)}° N` : "—"}
                            </span>
                        </div>

                        <div className="coordinate-card">
                            <div className="coordinate-label">
                                <MapPin size={12} color="var(--primary-green)" />
                                <span>Longitude</span>
                            </div>
                            <span className="coordinate-value">
                                {validationData?.centroid?.longitude ? `${validationData.centroid.longitude.toFixed(5)}° E` : "—"}
                            </span>
                        </div>
                    </div>

                    <div className="area-perimeter-grid">
                        <div className="metric-card">
                            <span className="metric-label">Area (Hectares)</span>
                            <span className="metric-value metric-value-green">
                                {validationData?.area_hectares ? `${validationData.area_hectares.toFixed(2)} ha` : "—"}
                            </span>
                        </div>

                        <div className="metric-card">
                            <span className="metric-label">Perimeter</span>
                            <span className="metric-value">
                                {validationData?.perimeter_m ? `${(validationData.perimeter_m / 1000).toFixed(2)} km` : "—"}
                            </span>
                        </div>
                    </div>

                    <hr style={{ border: 0, borderTop: "1px solid var(--border-color)" }} />

                    {/* Validation Summary checklist */}
                    <div className="validation-checklist">
                        <h4 className="checklist-title">
                            Field Validation Checklist
                        </h4>

                        <div className="checklist-items">
                            {/* Checkbox item: Boundary valid */}
                            <div className="checklist-item">
                                <div className={validationData?.geometry_valid ? "checklist-item-valid" : ""}>
                                    <CheckCircle size={16} fill={validationData?.geometry_valid ? "#d1fae5" : "transparent"} />
                                </div>
                                <span className={validationData?.geometry_valid ? "checklist-item-text" : "checklist-item-text-pending"}>Boundary Valid</span>
                            </div>

                            {/* Checkbox item: Coordinates valid */}
                            <div className="checklist-item">
                                <div className={validationData?.geometry_valid ? "checklist-item-valid" : ""}>
                                    <CheckCircle size={16} fill={validationData?.geometry_valid ? "#d1fae5" : "transparent"} />
                                </div>
                                <span className={validationData?.geometry_valid ? "checklist-item-text" : "checklist-item-text-pending"}>Coordinates Valid</span>
                            </div>

                            {/* Checkbox item: Geometry valid */}
                            <div className="checklist-item">
                                <div className={validationData?.geometry_valid ? "checklist-item-valid" : ""}>
                                    <CheckCircle size={16} fill={validationData?.geometry_valid ? "#d1fae5" : "transparent"} />
                                </div>
                                <span className={validationData?.geometry_valid ? "checklist-item-text" : "checklist-item-text-pending"}>Geometry Valid</span>
                            </div>

                            {/* Checkbox item: Area calculated */}
                            <div className="checklist-item">
                                <div className={validationData?.area_valid ? "checklist-item-valid" : ""}>
                                    <CheckCircle size={16} fill={validationData?.area_valid ? "#d1fae5" : "transparent"} />
                                </div>
                                <span className={validationData?.area_valid ? "checklist-item-text" : "checklist-item-text-pending"}>Area Calculated</span>
                            </div>

                            {/* Checkbox item: Location identified */}
                            <div className="checklist-item">
                                <div className={validationData?.location?.country ? "checklist-item-valid" : ""}>
                                    <CheckCircle size={16} fill={validationData?.location?.country ? "#d1fae5" : "transparent"} />
                                </div>
                                <span className={validationData?.location?.country ? "checklist-item-text" : "checklist-item-text-pending"}>Location Identified</span>
                            </div>
                        </div>

                        {/* Validation Badge */}
                        <div
                            style={{
                                marginTop: "8px",
                                padding: "8px 12px",
                                borderRadius: "6px",
                                backgroundColor: validationData?.valid ? "#ecfdf5" : "#f1f5f9",
                                color: validationData?.valid ? "#065f46" : "var(--text-muted)",
                                fontSize: "12px",
                                fontWeight: 600,
                                display: "flex",
                                alignItems: "center",
                                gap: "8px"
                            }}
                        >
                            <Info size={14} />
                            <span>Status: {isValidating ? "Validating field boundary..." : validationData?.valid ? "Ready for Analysis" : "Draw boundary to validate"}</span>
                        </div>
                    </div>
                </div>

            </div>

            {/* AI Field Verification Rejection Modal */}
            {aiRejectionData && (
                <div className="ai-verification-backdrop" onClick={() => setAiRejectionData(null)}>
                    <div className="ai-verification-modal" onClick={(e) => e.stopPropagation()}>
                        <div className="ai-modal-icon-wrapper">
                            <AlertTriangle size={32} />
                        </div>

                        <h3 className="ai-modal-title">Selected Region Is Not a Field</h3>

                        <p className="ai-modal-desc">
                            The selected boundary does not appear to be an agricultural field. Please select a valid cultivated farmland area.
                        </p>

                        {aiRejectionData.user_friendly_category && (
                            <div className="ai-detected-pill">
                                <strong>Detected:</strong>
                                <span>{aiRejectionData.user_friendly_category}</span>
                            </div>
                        )}

                        {aiRejectionData.reason && (
                            <div className="ai-reason-box">
                                <strong>AI Visual Analysis:</strong>
                                <span>{aiRejectionData.reason}</span>
                            </div>
                        )}

                        <div className="ai-modal-actions">
                            <button
                                className="ai-modal-btn-primary"
                                onClick={() => {
                                    setAiRejectionData(null);
                                    handleRedraw();
                                }}
                            >
                                <Trash2 size={16} />
                                <span>Try Another Region</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* AI Field Verification In-Progress Loading Modal */}
            {isVerifyingAI && (
                <div className="ai-verification-backdrop">
                    <div className="ai-verification-modal ai-verification-modal--loading">
                        <div className="ai-modal-icon-wrapper ai-modal-icon-wrapper--loading">
                            <Loader2 size={32} className="analysis-loading-spinner" />
                        </div>

                        <h3 className="ai-modal-title">Verifying selected field...</h3>

                        <p className="ai-modal-desc" style={{ marginBottom: 0 }}>
                            AI is checking whether the selected region appears to be agricultural farmland.
                        </p>
                    </div>
                </div>
            )}

            {/* AI Error Modal */}
            {aiErrorData && !aiRejectionData && (
                <div className="ai-verification-backdrop" onClick={() => setAiErrorData(null)}>
                    <div className="ai-verification-modal" onClick={(e) => e.stopPropagation()}>
                        <div className="ai-modal-icon-wrapper">
                            <AlertTriangle size={32} />
                        </div>

                        <h3 className="ai-modal-title">Verification Error</h3>

                        <p className="ai-modal-desc">
                            {aiErrorData}
                        </p>

                        <div className="ai-modal-actions">
                            <button
                                className="ai-modal-btn-secondary"
                                onClick={() => setAiErrorData(null)}
                            >
                                Cancel
                            </button>
                            <button
                                className="ai-modal-btn-primary"
                                onClick={() => {
                                    setAiErrorData(null);
                                    handleConfirmField();
                                }}
                            >
                                Retry Verification
                            </button>
                        </div>
                    </div>
                </div>
            )}
            
        </div>
    );
};

export default AreaSelection;
